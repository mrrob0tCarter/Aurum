import pandas_ta as ta

df["rsi_14"]   = ta.rsi(df["close"], length=14)
df["macd"]     = ta.macd(df["close"])["MACD_12_26_9"]
df["macd_sig"] = ta.macd(df["close"])["MACDs_12_26_9"]
df["atr_14"]   = ta.atr(df["high"], df["low"], df["close"], length=14)

# Support / resistance: rolling 180-day extremes
df["resistance"] = df["high"].rolling(180).max()
df["support"]    = df["low"].rolling(180).min()