#region Using declarations
using System;
using System.Collections.Generic;
#endregion

namespace NinjaTrader.NinjaScript.AddOns
{
	/// <summary>
	/// In-memory duplicate command-id cache with TTL window.
	/// </summary>
	public sealed class WebhookDuplicateCache
	{
		private readonly Dictionary<string, DateTime> _seen = new Dictionary<string, DateTime>(StringComparer.Ordinal);
		private readonly object _sync = new object();
		private TimeSpan _window;

		public WebhookDuplicateCache(int windowSeconds)
		{
			SetWindowSeconds(windowSeconds);
		}

		public void SetWindowSeconds(int windowSeconds)
		{
			if (windowSeconds < 1)
				windowSeconds = 1;
			_window = TimeSpan.FromSeconds(windowSeconds);
		}

		public bool TryAccept(string commandId)
		{
			if (string.IsNullOrWhiteSpace(commandId))
				return false;

			lock (_sync)
			{
				PruneUnlocked(DateTime.UtcNow);

				DateTime previous;
				if (_seen.TryGetValue(commandId, out previous) && DateTime.UtcNow - previous < _window)
					return false;

				_seen[commandId] = DateTime.UtcNow;
				return true;
			}
		}

		private void PruneUnlocked(DateTime now)
		{
			var expired = new List<string>();
			foreach (var pair in _seen)
			{
				if (now - pair.Value >= _window)
					expired.Add(pair.Key);
			}

			for (int i = 0; i < expired.Count; i++)
				_seen.Remove(expired[i]);
		}
	}
}
