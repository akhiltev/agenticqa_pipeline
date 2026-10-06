# Feature Spec: Robust JSON Number Parsing

## Summary
JSON-java's parser should never throw an unhandled runtime exception when
presented with extremely large or malformed numeric literals. Callers should
be able to safely fall back to a default value.

## Requirements
- Parsing a JSON number with an extremely large number of digits must not
  crash the tokenizer/parser.
- `JSONObject.optBigDecimal(key, defaultValue)` must return `defaultValue`
  when the stored value cannot be converted to a `BigDecimal`.
- Normal-sized numeric values must continue to parse exactly as before.

## Out of scope
- Changing the public signature of any existing method.
