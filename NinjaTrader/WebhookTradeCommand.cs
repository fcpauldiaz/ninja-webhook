#region Using declarations
using System;
using System.Globalization;
using System.Text;
#endregion

namespace NinjaTrader.NinjaScript.AddOns
{
	/// <summary>
	/// Trade command payload. Parsed with a small hand-rolled JSON reader
	/// so we do not depend on System.Runtime.Serialization.Json in NinjaScript.
	/// </summary>
	public class WebhookTradeCommand
	{
		public string Id { get; set; }
		public string Timestamp { get; set; }
		public string Source { get; set; }
		public string Symbol { get; set; }
		public string NtSymbol { get; set; }
		public string Action { get; set; }
		public string OrderType { get; set; }
		public int Quantity { get; set; }
		public string Account { get; set; }
		public string TimeInForce { get; set; }
		public string Comment { get; set; }
		public int StopLossTicks { get; set; }
		public int ProfitTargetTicks { get; set; }

		public static bool TryParse(string jsonLine, out WebhookTradeCommand command, out string error)
		{
			command = null;
			error = null;

			if (string.IsNullOrWhiteSpace(jsonLine))
			{
				error = "Empty JSON line.";
				return false;
			}

			try
			{
				command = new WebhookTradeCommand
				{
					Id = ReadString(jsonLine, "id"),
					Timestamp = ReadString(jsonLine, "timestamp"),
					Source = ReadString(jsonLine, "source"),
					Symbol = ReadString(jsonLine, "symbol"),
					NtSymbol = ReadString(jsonLine, "ntSymbol"),
					Action = ReadString(jsonLine, "action"),
					OrderType = ReadString(jsonLine, "orderType"),
					Account = ReadString(jsonLine, "account"),
					TimeInForce = ReadString(jsonLine, "timeInForce"),
					Comment = ReadString(jsonLine, "comment"),
					Quantity = ReadInt(jsonLine, "quantity"),
					StopLossTicks = ReadInt(jsonLine, "stopLossTicks"),
					ProfitTargetTicks = ReadInt(jsonLine, "profitTargetTicks")
				};

				Normalize(command);
				return true;
			}
			catch (Exception ex)
			{
				command = null;
				error = "Malformed JSON: " + ex.Message;
				return false;
			}
		}

		private static void Normalize(WebhookTradeCommand command)
		{
			command.Id = TrimOrNull(command.Id);
			command.Timestamp = TrimOrNull(command.Timestamp);
			command.Source = TrimOrNull(command.Source);
			command.Symbol = TrimOrNull(command.Symbol);
			command.NtSymbol = TrimOrNull(command.NtSymbol);
			command.Action = UpperOrNull(command.Action);
			command.OrderType = UpperOrNull(command.OrderType) ?? "MARKET";
			command.Account = TrimOrNull(command.Account);
			command.TimeInForce = UpperOrNull(command.TimeInForce) ?? "DAY";
			command.Comment = TrimOrNull(command.Comment);
		}

		private static string TrimOrNull(string value)
		{
			if (string.IsNullOrWhiteSpace(value))
				return null;
			return value.Trim();
		}

		private static string UpperOrNull(string value)
		{
			if (string.IsNullOrWhiteSpace(value))
				return null;
			return value.Trim().ToUpperInvariant();
		}

		private static int ReadInt(string json, string name)
		{
			string raw = ReadRawValue(json, name);
			if (string.IsNullOrWhiteSpace(raw))
				return 0;

			raw = raw.Trim().Trim('"');
			int value;
			if (int.TryParse(raw, NumberStyles.Integer, CultureInfo.InvariantCulture, out value))
				return value;
			return 0;
		}

		private static string ReadString(string json, string name)
		{
			string raw = ReadRawValue(json, name);
			if (raw == null)
				return null;

			raw = raw.Trim();
			if (raw.Length >= 2 && raw[0] == '"' && raw[raw.Length - 1] == '"')
				return UnescapeJson(raw.Substring(1, raw.Length - 2));

			if (string.Equals(raw, "null", StringComparison.OrdinalIgnoreCase))
				return null;

			return raw;
		}

		private static string ReadRawValue(string json, string name)
		{
			string key = "\"" + name + "\"";
			int keyIndex = IndexOfPropertyKey(json, key);
			if (keyIndex < 0)
				return null;

			int colon = json.IndexOf(':', keyIndex + key.Length);
			if (colon < 0)
				return null;

			int i = colon + 1;
			while (i < json.Length && char.IsWhiteSpace(json[i]))
				i++;

			if (i >= json.Length)
				return null;

			if (json[i] == '"')
			{
				int end = i + 1;
				while (end < json.Length)
				{
					if (json[end] == '\\')
					{
						end += 2;
						continue;
					}
					if (json[end] == '"')
						break;
					end++;
				}

				if (end >= json.Length)
					return null;

				return json.Substring(i, end - i + 1);
			}

			int start = i;
			while (i < json.Length && json[i] != ',' && json[i] != '}' && !char.IsWhiteSpace(json[i]))
				i++;

			return json.Substring(start, i - start);
		}

		private static int IndexOfPropertyKey(string json, string key)
		{
			int index = 0;
			while (index < json.Length)
			{
				int found = json.IndexOf(key, index, StringComparison.Ordinal);
				if (found < 0)
					return -1;

				// Require the key to look like a property name (preceded by { or ,).
				int lookback = found - 1;
				while (lookback >= 0 && char.IsWhiteSpace(json[lookback]))
					lookback--;

				if (lookback < 0 || json[lookback] == '{' || json[lookback] == ',')
					return found;

				index = found + key.Length;
			}

			return -1;
		}

		private static string UnescapeJson(string value)
		{
			if (value.IndexOf('\\') < 0)
				return value;

			var sb = new StringBuilder(value.Length);
			for (int i = 0; i < value.Length; i++)
			{
				char c = value[i];
				if (c != '\\' || i + 1 >= value.Length)
				{
					sb.Append(c);
					continue;
				}

				char next = value[++i];
				switch (next)
				{
					case '"': sb.Append('"'); break;
					case '\\': sb.Append('\\'); break;
					case '/': sb.Append('/'); break;
					case 'b': sb.Append('\b'); break;
					case 'f': sb.Append('\f'); break;
					case 'n': sb.Append('\n'); break;
					case 'r': sb.Append('\r'); break;
					case 't': sb.Append('\t'); break;
					default: sb.Append(next); break;
				}
			}

			return sb.ToString();
		}

		public override string ToString()
		{
			return string.Format(CultureInfo.InvariantCulture,
				"id={0} action={1} ntSymbol={2} qty={3} account={4} orderType={5} slTicks={6} ptTicks={7}",
				Id, Action, NtSymbol, Quantity, Account, OrderType, StopLossTicks, ProfitTargetTicks);
		}
	}
}
