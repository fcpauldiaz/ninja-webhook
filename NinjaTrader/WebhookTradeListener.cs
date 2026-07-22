#region Using declarations
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Windows;
using System.Windows.Automation;
using System.Windows.Controls;
using System.Windows.Media;
using NinjaTrader.Cbi;
using NinjaTrader.Gui;
using NinjaTrader.Gui.Tools;
using NinjaTrader.NinjaScript;
#endregion

namespace NinjaTrader.NinjaScript.AddOns
{
	public class WebhookTradeListener : AddOnBase
	{
		private const string MenuAutomationId = "WebhookTradeListenerMenuItem";
		private NTMenuItem _menuItem;
		private NTMenuItem _parentMenu;
		private bool _autoOpened;

		protected override void OnStateChange()
		{
			if (State == State.SetDefaults)
			{
				Description = @"Localhost TCP listener that receives webhook trade commands and submits orders.";
				Name = "WebhookTradeListener";
			}
		}

		protected override void OnWindowCreated(Window window)
		{
			ControlCenter controlCenter = window as ControlCenter;
			if (controlCenter == null)
				return;

			try
			{
				InstallMenu(controlCenter);
				AutoOpenWindow();
			}
			catch (Exception ex)
			{
				NinjaTrader.Code.Output.Process(
					DateTime.Now.ToString("HH:mm:ss") + " [WebhookTradeListener] menu install failed: " + ex.Message,
					PrintTo.OutputTab1);
			}
		}

		private void InstallMenu(ControlCenter controlCenter)
		{
			// Remove any stale menu item left from a previous compile (dead Click handlers).
			DependencyObject existing = controlCenter.FindFirst(MenuAutomationId);
			if (existing != null)
			{
				NTMenuItem stale = existing as NTMenuItem;
				if (stale != null)
				{
					NTMenuItem parent = stale.Parent as NTMenuItem;
					if (parent != null && parent.Items.Contains(stale))
						parent.Items.Remove(stale);
					else if (controlCenter.MainMenu != null && controlCenter.MainMenu.Contains(stale))
						controlCenter.MainMenu.Remove(stale);
				}
			}

			_menuItem = new NTMenuItem
			{
				Header = "Webhook Trade Listener",
				Style = Application.Current.TryFindResource("MainMenuItem") as Style
			};
			AutomationProperties.SetAutomationId(_menuItem, MenuAutomationId);
			_menuItem.Click += OnMenuClick;

			// Prefer New menu; fall back to Tools; finally add as top-level Control Center menu.
			_parentMenu = controlCenter.FindFirst("ControlCenterMenuItemNew") as NTMenuItem;
			if (_parentMenu == null)
				_parentMenu = controlCenter.FindFirst("ControlCenterMenuItemTools") as NTMenuItem;

			if (_parentMenu != null)
			{
				_parentMenu.Items.Add(_menuItem);
				NinjaTrader.Code.Output.Process(
					"[WebhookTradeListener] Menu installed under " + Convert.ToString(_parentMenu.Header),
					PrintTo.OutputTab1);
				return;
			}

			if (controlCenter.MainMenu != null)
			{
				controlCenter.MainMenu.Add(_menuItem);
				_parentMenu = null;
				NinjaTrader.Code.Output.Process(
					"[WebhookTradeListener] Menu installed as top-level Control Center item",
					PrintTo.OutputTab1);
				return;
			}

			NinjaTrader.Code.Output.Process(
				"[WebhookTradeListener] Could not find Control Center menu to attach to",
				PrintTo.OutputTab1);
		}

		private void AutoOpenWindow()
		{
			if (_autoOpened)
				return;

			_autoOpened = true;
			DispatchToUi(ShowOrActivateWindow);
		}

		protected override void OnWindowDestroyed(Window window)
		{
			if (!(window is ControlCenter) || _menuItem == null)
				return;

			_menuItem.Click -= OnMenuClick;

			if (_parentMenu != null && _parentMenu.Items.Contains(_menuItem))
				_parentMenu.Items.Remove(_menuItem);
			else
			{
				ControlCenter cc = window as ControlCenter;
				if (cc != null && cc.MainMenu != null && cc.MainMenu.Contains(_menuItem))
					cc.MainMenu.Remove(_menuItem);
			}

			_menuItem = null;
			_parentMenu = null;
			_autoOpened = false;
		}

		private void OnMenuClick(object sender, RoutedEventArgs e)
		{
			NinjaTrader.Code.Output.Process("[WebhookTradeListener] Menu clicked — opening window...", PrintTo.OutputTab1);
			DispatchToUi(ShowOrActivateWindow);
		}

		private static void DispatchToUi(Action action)
		{
			Application app = Application.Current;
			if (app == null)
			{
				NinjaTrader.Code.Output.Process("[WebhookTradeListener] Application.Current is null", PrintTo.OutputTab1);
				return;
			}

			if (app.Dispatcher.CheckAccess())
				action();
			else
				app.Dispatcher.BeginInvoke(action);
		}

		private static void ShowOrActivateWindow()
		{
			try
			{
				foreach (Window window in Application.Current.Windows)
				{
					WebhookTradeListenerWindow existing = window as WebhookTradeListenerWindow;
					if (existing != null)
					{
						if (existing.WindowState == WindowState.Minimized)
							existing.WindowState = WindowState.Normal;
						existing.Activate();
						existing.Topmost = true;
						existing.Topmost = false;
						NinjaTrader.Code.Output.Process("[WebhookTradeListener] Activated existing window", PrintTo.OutputTab1);
						return;
					}
				}

				WebhookTradeListenerWindow win = new WebhookTradeListenerWindow();
				win.Show();
				win.Activate();
				NinjaTrader.Code.Output.Process("[WebhookTradeListener] Window opened", PrintTo.OutputTab1);
			}
			catch (Exception ex)
			{
				NinjaTrader.Code.Output.Process(
					"[WebhookTradeListener] Failed to open window: " + ex,
					PrintTo.OutputTab1);
			}
		}
	}

	public class WebhookTradeListenerWindow : Window
	{
		private CheckBox _enableLiveTrading;
		private TextBox _tcpPort;
		private ComboBox _accountSelector;
		private ComboBox _instrumentSelector;
		private TextBox _quantityField;
		private TextBox _dedupeSeconds;
		private TextBlock _statusText;
		private TextBlock _lastCommandText;
		private TextBlock _lastErrorText;
		private Button _startButton;
		private Button _stopButton;

		private TcpListener _listener;
		private Thread _acceptThread;
		private volatile bool _running;
		private volatile bool _liveTradingEnabled;
		private volatile string _configuredAccount = "Sim101";
		private volatile string _configuredInstrument = "ES 09-26";
		private volatile int _configuredQuantity = 1;
		private WebhookDuplicateCache _dedupe = new WebhookDuplicateCache(300);
		private readonly object _logSync = new object();

		private static readonly string[] DefaultInstruments =
		{
			"ES 09-26",
			"MES 09-26",
			"NQ 09-26",
			"MNQ 09-26",
			"YM 09-26",
			"MYM 09-26",
			"RTY 09-26",
			"M2K 09-26"
		};

		public WebhookTradeListenerWindow()
		{
			Title = "Webhook Trade Listener";
			Width = 520;
			Height = 540;
			WindowStartupLocation = WindowStartupLocation.CenterScreen;
			Background = Brushes.WhiteSmoke;
			Content = BuildUi();
			Closing += OnClosing;
			Loaded += (s, e) => UpdateUiState();
		}

		private FrameworkElement BuildUi()
		{
			var root = new Grid { Margin = new Thickness(12) };
			root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
			root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
			root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
			root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
			root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
			root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
			root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
			root.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
			root.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

			_tcpPort = AddLabeledField(root, 0, "TCP Port (127.0.0.1 only)", "7077");
			_accountSelector = AddAccountSelector(root, 1, "Account");
			_instrumentSelector = AddInstrumentSelector(root, 2, "Instrument");
			_quantityField = AddLabeledField(root, 3, "Quantity", "1");
			_quantityField.TextChanged += (s, e) =>
			{
				int parsed;
				if (int.TryParse((_quantityField.Text ?? string.Empty).Trim(), out parsed) && parsed > 0)
					_configuredQuantity = parsed;
			};
			_dedupeSeconds = AddLabeledField(root, 4, "Dedupe Window Seconds", "300");

			var buttons = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 8, 0, 8) };
			_startButton = new Button { Content = "Start Listener", Width = 140, Margin = new Thickness(0, 0, 8, 0) };
			_stopButton = new Button { Content = "Stop Listener", Width = 140, IsEnabled = false };
			_startButton.Click += (s, e) => StartListener();
			_stopButton.Click += (s, e) => StopListener();
			buttons.Children.Add(_startButton);
			buttons.Children.Add(_stopButton);
			Grid.SetRow(buttons, 5);
			root.Children.Add(buttons);

			_enableLiveTrading = new CheckBox
			{
				Content = "ENABLE LIVE TRADING",
				IsChecked = false,
				Margin = new Thickness(0, 8, 0, 12),
				FontSize = 16,
				FontWeight = FontWeights.Bold,
				Foreground = Brushes.DarkRed,
				Padding = new Thickness(4)
			};
			_enableLiveTrading.Checked += (s, e) =>
			{
				_liveTradingEnabled = true;
				_enableLiveTrading.Foreground = Brushes.DarkGreen;
				_enableLiveTrading.Content = "LIVE TRADING ENABLED";
				Log("EnableLiveTrading=ON");
			};
			_enableLiveTrading.Unchecked += (s, e) =>
			{
				_liveTradingEnabled = false;
				_enableLiveTrading.Foreground = Brushes.DarkRed;
				_enableLiveTrading.Content = "ENABLE LIVE TRADING";
				Log("EnableLiveTrading=OFF");
			};
			Grid.SetRow(_enableLiveTrading, 6);
			root.Children.Add(_enableLiveTrading);

			var statusPanel = new StackPanel();
			_statusText = new TextBlock { Text = "Status: Stopped", FontWeight = FontWeights.SemiBold, Margin = new Thickness(0, 4, 0, 4) };
			_lastCommandText = new TextBlock { Text = "Last command: -", TextWrapping = TextWrapping.Wrap, Margin = new Thickness(0, 2, 0, 2) };
			_lastErrorText = new TextBlock { Text = "Last error: -", TextWrapping = TextWrapping.Wrap, Foreground = Brushes.DarkRed, Margin = new Thickness(0, 2, 0, 2) };
			statusPanel.Children.Add(_statusText);
			statusPanel.Children.Add(_lastCommandText);
			statusPanel.Children.Add(_lastErrorText);
			Grid.SetRow(statusPanel, 7);
			root.Children.Add(statusPanel);

			var note = new TextBlock
			{
				Text = "Account, Instrument, and Quantity come from this panel only (alert symbol/qty ignored). Keep a live chart/DOM open so brackets can read bid/ask. Listener binds to 127.0.0.1 only.",
				TextWrapping = TextWrapping.Wrap,
				Margin = new Thickness(0, 12, 0, 0),
				Opacity = 0.85
			};
			Grid.SetRow(note, 8);
			root.Children.Add(note);

			return root;
		}

		private ComboBox AddAccountSelector(Grid root, int row, string label)
		{
			var panel = new StackPanel { Margin = new Thickness(0, 0, 0, 6) };
			panel.Children.Add(new TextBlock { Text = label, Margin = new Thickness(0, 0, 0, 2) });

			var combo = new ComboBox { IsEditable = false };
			RefreshAccountSelector(combo);
			combo.DropDownOpened += (s, e) => RefreshAccountSelector(combo);
			combo.SelectionChanged += (s, e) =>
			{
				_configuredAccount = combo.SelectedItem as string ?? string.Empty;
			};

			panel.Children.Add(combo);
			Grid.SetRow(panel, row);
			root.Children.Add(panel);
			return combo;
		}

		private ComboBox AddInstrumentSelector(Grid root, int row, string label)
		{
			var panel = new StackPanel { Margin = new Thickness(0, 0, 0, 6) };
			panel.Children.Add(new TextBlock { Text = label, Margin = new Thickness(0, 0, 0, 2) });

			var combo = new ComboBox { IsEditable = true };
			for (int i = 0; i < DefaultInstruments.Length; i++)
				combo.Items.Add(DefaultInstruments[i]);
			combo.SelectedItem = "ES 09-26";
			combo.Text = "ES 09-26";
			_configuredInstrument = "ES 09-26";

			combo.SelectionChanged += (s, e) =>
			{
				string selected = combo.SelectedItem as string;
				if (!string.IsNullOrWhiteSpace(selected))
					_configuredInstrument = selected.Trim();
			};
			combo.LostFocus += (s, e) =>
			{
				string typed = (combo.Text ?? string.Empty).Trim();
				if (!string.IsNullOrWhiteSpace(typed))
					_configuredInstrument = typed;
			};

			panel.Children.Add(combo);
			Grid.SetRow(panel, row);
			root.Children.Add(panel);
			return combo;
		}

		private void RefreshAccountSelector(ComboBox combo)
		{
			string previous = combo.SelectedItem as string ?? _configuredAccount;
			combo.Items.Clear();

			List<string> names = GetAccountNames();
			for (int i = 0; i < names.Count; i++)
				combo.Items.Add(names[i]);

			if (names.Count == 0)
			{
				_configuredAccount = string.Empty;
				combo.SelectedIndex = -1;
				return;
			}

			string preferred = names.FirstOrDefault(n => string.Equals(n, previous, StringComparison.OrdinalIgnoreCase));
			if (preferred == null)
				preferred = names.FirstOrDefault(n => string.Equals(n, "Sim101", StringComparison.OrdinalIgnoreCase));
			if (preferred != null)
				combo.SelectedItem = preferred;
			else
				combo.SelectedIndex = 0;

			_configuredAccount = combo.SelectedItem as string ?? string.Empty;
		}

		private static List<string> GetAccountNames()
		{
			var names = new List<string>();
			try
			{
				lock (Account.All)
				{
					foreach (Account account in Account.All)
					{
						if (account == null || string.IsNullOrWhiteSpace(account.Name))
							continue;
						if (account.ConnectionStatus != ConnectionStatus.Connected)
							continue;
						if (!names.Contains(account.Name))
							names.Add(account.Name);
					}
				}
			}
			catch
			{
				// Account list may be unavailable during early UI build.
			}

			names.Sort(StringComparer.OrdinalIgnoreCase);
			return names;
		}

		private static TextBox AddLabeledField(Grid root, int row, string label, string defaultValue)
		{
			var panel = new StackPanel { Margin = new Thickness(0, 0, 0, 6) };
			panel.Children.Add(new TextBlock { Text = label, Margin = new Thickness(0, 0, 0, 2) });
			var box = new TextBox { Text = defaultValue };
			panel.Children.Add(box);
			Grid.SetRow(panel, row);
			root.Children.Add(panel);
			return box;
		}

		private void OnClosing(object sender, System.ComponentModel.CancelEventArgs e)
		{
			StopListener();
		}

		private void StartListener()
		{
			if (_running)
				return;

			int port;
			if (!int.TryParse(_tcpPort.Text.Trim(), out port) || port <= 0 || port > 65535)
			{
				SetError("Invalid TCP port.");
				return;
			}

			int dedupeSeconds;
			if (!int.TryParse(_dedupeSeconds.Text.Trim(), out dedupeSeconds) || dedupeSeconds < 1)
				dedupeSeconds = 300;
			_dedupe.SetWindowSeconds(dedupeSeconds);

			try
			{
				_listener = new TcpListener(IPAddress.Loopback, port);
				_listener.Start();
				_running = true;

				_acceptThread = new Thread(AcceptLoop)
				{
					IsBackground = true,
					Name = "WebhookTradeListenerAccept"
				};
				_acceptThread.Start();

				SetStatus("Listening on 127.0.0.1:" + port);
				Log("Listener started on 127.0.0.1:" + port);
				UpdateUiState();
			}
			catch (Exception ex)
			{
				_running = false;
				SetError("Failed to start listener: " + ex.Message);
				Log("ERROR starting listener: " + ex);
			}
		}

		private void StopListener()
		{
			_running = false;

			try
			{
				if (_listener != null)
					_listener.Stop();
			}
			catch
			{
				// ignored during shutdown
			}

			_listener = null;

			try
			{
				if (_acceptThread != null && _acceptThread.IsAlive)
					_acceptThread.Join(1000);
			}
			catch
			{
				// ignored
			}

			_acceptThread = null;
			SetStatus("Stopped");
			Log("Listener stopped.");
			UpdateUiState();
		}

		private void AcceptLoop()
		{
			while (_running)
			{
				try
				{
					var client = _listener.AcceptTcpClient();
					var thread = new Thread(() => HandleClient(client))
					{
						IsBackground = true,
						Name = "WebhookTradeListenerClient"
					};
					thread.Start();
				}
				catch (SocketException)
				{
					if (!_running)
						break;
				}
				catch (ObjectDisposedException)
				{
					break;
				}
				catch (Exception ex)
				{
					Log("Accept loop error: " + ex.Message);
					Ui(() => SetError(ex.Message));
				}
			}
		}

		private void HandleClient(TcpClient client)
		{
			try
			{
				using (client)
				using (var stream = client.GetStream())
				using (var reader = new StreamReader(stream, Encoding.UTF8))
				{
					string line;
					while (_running && (line = reader.ReadLine()) != null)
					{
						if (string.IsNullOrWhiteSpace(line))
							continue;

						ProcessCommandLine(line);
					}
				}
			}
			catch (Exception ex)
			{
				Log("Client disconnected/error: " + ex.Message);
			}
		}

		private void ProcessCommandLine(string line)
		{
			Log("Received: " + line);

			WebhookTradeCommand command;
			string parseError;
			if (!WebhookTradeCommand.TryParse(line, out command, out parseError))
			{
				Log("Rejected malformed JSON: " + parseError);
				Ui(() => SetError(parseError));
				return;
			}

			Ui(() => _lastCommandText.Text = "Last command: " + command);

			string rejectReason;
			if (!ValidateCommand(command, out rejectReason))
			{
				Log("Rejected command " + command.Id + ": " + rejectReason);
				Ui(() => SetError(rejectReason));
				return;
			}

			if (!_dedupe.TryAccept(command.Id))
			{
				var msg = "Duplicate command id within window: " + command.Id;
				Log("Rejected: " + msg);
				Ui(() => SetError(msg));
				return;
			}

			if (!_liveTradingEnabled)
			{
				Log("SIMULATION (EnableLiveTrading=false): accepted but NOT submitted -> " + command);
				Ui(() => SetStatus("Dry/Sim accepted: " + command.Id));
				return;
			}

			Log("EnableLiveTrading=true — executing " + command);

			try
			{
				ExecuteCommand(command);
				Log("Order path completed for command " + command.Id);
				Ui(() => SetStatus("Submitted: " + command.Id));
			}
			catch (Exception ex)
			{
				Log("ERROR executing command " + command.Id + ": " + ex);
				Ui(() => SetError(ex.Message));
			}
		}

		private bool ValidateCommand(WebhookTradeCommand command, out string reason)
		{
			reason = null;

			if (string.IsNullOrWhiteSpace(command.Id))
			{
				reason = "id is required.";
				return false;
			}

			if (string.IsNullOrWhiteSpace(command.Action))
			{
				reason = "action is required.";
				return false;
			}

			if (command.Action != "BUY" && command.Action != "SELL" &&
				command.Action != "EXIT_LONG" && command.Action != "EXIT_SHORT" &&
				command.Action != "FLATTEN")
			{
				reason = "Unsupported action: " + command.Action;
				return false;
			}

			if (!string.Equals(command.OrderType, "MARKET", StringComparison.OrdinalIgnoreCase))
			{
				reason = "Only MARKET orderType is supported.";
				return false;
			}

			if (command.Action == "BUY" || command.Action == "SELL")
			{
				int panelQty = GetPanelQuantity();
				if (panelQty < 1)
				{
					reason = "Quantity must be > 0 in the listener panel.";
					return false;
				}
			}

			string panelInstrument = GetPanelInstrumentName();
			if (string.IsNullOrWhiteSpace(panelInstrument))
			{
				reason = "Instrument is required in the listener panel.";
				return false;
			}

			return true;
		}

		private int GetPanelQuantity()
		{
			int fromField = UiGet(() =>
			{
				int parsed;
				if (!int.TryParse((_quantityField.Text ?? string.Empty).Trim(), out parsed) || parsed < 1)
					return 0;
				return parsed;
			});
			if (fromField > 0)
				return fromField;
			return _configuredQuantity > 0 ? _configuredQuantity : 1;
		}

		private string GetPanelInstrumentName()
		{
			string fromUi = UiGet(() =>
			{
				string selected = _instrumentSelector.SelectedItem as string;
				if (!string.IsNullOrWhiteSpace(selected))
					return selected.Trim();
				return (_instrumentSelector.Text ?? string.Empty).Trim();
			});
			if (!string.IsNullOrWhiteSpace(fromUi))
				return fromUi;
			return _configuredInstrument;
		}

		private void ExecuteCommand(WebhookTradeCommand command)
		{
			// Account, instrument, and quantity always come from the listener panel.
			string accountName = _configuredAccount;
			if (string.IsNullOrWhiteSpace(accountName))
				accountName = UiGet(() => _accountSelector.SelectedItem as string);
			if (string.IsNullOrWhiteSpace(accountName))
				accountName = "Sim101";

			string instrumentName = GetPanelInstrumentName();
			if (string.IsNullOrWhiteSpace(instrumentName))
				instrumentName = "ES 09-26";

			int quantity = GetPanelQuantity();

			Log("Using panel account=" + accountName + " instrument=" + instrumentName + " qty=" + quantity);

			Account account;
			lock (Account.All)
			{
				account = Account.All.FirstOrDefault(a => string.Equals(a.Name, accountName, StringComparison.OrdinalIgnoreCase));
			}

			if (account == null)
				throw new InvalidOperationException("Account not found: " + accountName);

			Instrument instrument = Instrument.GetInstrument(instrumentName);
			if (instrument == null)
				throw new InvalidOperationException("Instrument not found: " + instrumentName);

			TimeInForce tif = TimeInForce.Day;
			if (string.Equals(command.TimeInForce, "GTC", StringComparison.OrdinalIgnoreCase))
				tif = TimeInForce.Gtc;

			string signal = string.IsNullOrWhiteSpace(command.Comment) ? "WH-" + command.Id : command.Comment;
			if (signal.Length > 50)
				signal = signal.Substring(0, 50);

			if (command.Action == "FLATTEN")
			{
				Log("Submitting Flatten for " + instrument.FullName + " on " + account.Name);
				account.Flatten(new[] { instrument });
				return;
			}

			if (command.Action == "EXIT_LONG" || command.Action == "EXIT_SHORT")
			{
				Position position = account.Positions.FirstOrDefault(p => p.Instrument == instrument);
				if (position == null || position.MarketPosition == MarketPosition.Flat)
				{
					Log("No matching position to exit for " + instrument.FullName);
					return;
				}

				bool wantLong = command.Action == "EXIT_LONG";
				if (wantLong && position.MarketPosition != MarketPosition.Long)
				{
					Log("EXIT_LONG ignored; position is " + position.MarketPosition);
					return;
				}

				if (!wantLong && position.MarketPosition != MarketPosition.Short)
				{
					Log("EXIT_SHORT ignored; position is " + position.MarketPosition);
					return;
				}

				// Futures-friendly close: Sell long / Buy short covering.
				OrderAction closeAction = position.MarketPosition == MarketPosition.Long
					? OrderAction.Sell
					: OrderAction.Buy;

				SubmitMarket(account, instrument, closeAction, position.Quantity, tif, signal);
				return;
			}

			OrderAction entryAction = command.Action == "BUY" ? OrderAction.Buy : OrderAction.Sell;
			SubmitMarket(
				account,
				instrument,
				entryAction,
				quantity,
				tif,
				signal,
				command.StopLossTicks,
				command.ProfitTargetTicks);
		}

		private void SubmitMarket(
			Account account,
			Instrument instrument,
			OrderAction action,
			int quantity,
			TimeInForce tif,
			string signal,
			int stopLossTicks = 0,
			int profitTargetTicks = 0)
		{
			bool isBracket = stopLossTicks > 0 && profitTargetTicks > 0
				&& (action == OrderAction.Buy || action == OrderAction.Sell);

			Log(string.Format("Submitting {0} MARKET qty={1} {2} account={3} signal={4} bracket={5} sl={6} pt={7}",
				action, quantity, instrument.FullName, account.Name, signal, isBracket, stopLossTicks, profitTargetTicks));

			Order entry = account.CreateOrder(
				instrument,
				action,
				OrderType.Market,
				OrderEntry.Manual,
				tif,
				quantity,
				0,
				0,
				string.Empty,
				signal,
				Core.Globals.MinDate,
				null);

			if (!isBracket)
			{
				account.Submit(new[] { entry });
				Log("Order submitted: " + entry.OrderId + " / " + entry.Name);
				return;
			}

			double tickSize = instrument.MasterInstrument.TickSize;
			if (tickSize <= 0)
				throw new InvalidOperationException("Invalid tick size for " + instrument.FullName);

			double refPrice = GetReferencePrice(instrument, action);
			if (refPrice <= 0)
				throw new InvalidOperationException("No market price available for bracket on " + instrument.FullName);

			bool isLong = action == OrderAction.Buy;
			double stopPrice = isLong
				? refPrice - stopLossTicks * tickSize
				: refPrice + stopLossTicks * tickSize;
			double targetPrice = isLong
				? refPrice + profitTargetTicks * tickSize
				: refPrice - profitTargetTicks * tickSize;

			stopPrice = instrument.MasterInstrument.RoundToTickSize(stopPrice);
			targetPrice = instrument.MasterInstrument.RoundToTickSize(targetPrice);

			OrderAction exitAction = isLong ? OrderAction.Sell : OrderAction.Buy;
			string oco = Guid.NewGuid().ToString("N");

			string stopName = TruncateSignal(signal + "-SL");
			string targetName = TruncateSignal(signal + "-PT");

			Order stop = account.CreateOrder(
				instrument,
				exitAction,
				OrderType.StopMarket,
				OrderEntry.Manual,
				tif,
				quantity,
				0,
				stopPrice,
				oco,
				stopName,
				Core.Globals.MinDate,
				null);

			Order target = account.CreateOrder(
				instrument,
				exitAction,
				OrderType.Limit,
				OrderEntry.Manual,
				tif,
				quantity,
				targetPrice,
				0,
				oco,
				targetName,
				Core.Globals.MinDate,
				null);

			account.Submit(new[] { entry, stop, target });
			Log(string.Format(
				"Bracket submitted entry={0} stop={1}@{2} target={3}@{4} ref={5} oco={6}",
				entry.OrderId, stop.OrderId, stopPrice, target.OrderId, targetPrice, refPrice, oco));
		}

		private static double GetReferencePrice(Instrument instrument, OrderAction action)
		{
			try
			{
				if (instrument.MarketData == null)
					return 0;

				if (action == OrderAction.Buy && instrument.MarketData.Ask != null && instrument.MarketData.Ask.Price > 0)
					return instrument.MarketData.Ask.Price;

				if (action == OrderAction.Sell && instrument.MarketData.Bid != null && instrument.MarketData.Bid.Price > 0)
					return instrument.MarketData.Bid.Price;

				if (instrument.MarketData.Last != null && instrument.MarketData.Last.Price > 0)
					return instrument.MarketData.Last.Price;
			}
			catch
			{
				// Market data may be unavailable if instrument is not subscribed.
			}

			return 0;
		}

		private static string TruncateSignal(string signal)
		{
			if (string.IsNullOrEmpty(signal))
				return "WH";
			return signal.Length <= 50 ? signal : signal.Substring(0, 50);
		}

		private void UpdateUiState()
		{
			_startButton.IsEnabled = !_running;
			_stopButton.IsEnabled = _running;
			_tcpPort.IsEnabled = !_running;
			_accountSelector.IsEnabled = !_running;
			_instrumentSelector.IsEnabled = !_running;
			_quantityField.IsEnabled = !_running;
		}

		private void SetStatus(string text)
		{
			_statusText.Text = "Status: " + text;
		}

		private void SetError(string text)
		{
			_lastErrorText.Text = "Last error: " + text;
		}

		private void Ui(Action action)
		{
			if (Dispatcher.CheckAccess())
				action();
			else
				Dispatcher.InvokeAsync(action);
		}

		private T UiGet<T>(Func<T> func)
		{
			if (Dispatcher.CheckAccess())
				return func();

			T result = default(T);
			Dispatcher.Invoke(new Action(() => { result = func(); }));
			return result;
		}

		private void Log(string message)
		{
			string line = DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss.fff") + " [WebhookTradeListener] " + message;
			NinjaTrader.Code.Output.Process(line, PrintTo.OutputTab1);

			try
			{
				string documents = Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments);
				string dir = Path.Combine(documents, "WebhookNt8Bridge", "logs");
				Directory.CreateDirectory(dir);
				string path = Path.Combine(dir, "nt-listener.log");

				lock (_logSync)
				{
					File.AppendAllText(path, line + Environment.NewLine);
				}
			}
			catch
			{
				// File logging is best-effort and must never break trading path.
			}
		}
	}
}
