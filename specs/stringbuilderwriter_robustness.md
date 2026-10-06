# Feature Spec: StringBuilderWriter Robustness

## Summary
`StringBuilderWriter` (a performance-optimized alternative to
`java.io.StringWriter`) should correctly implement all inherited `Writer`
methods, including bounds checking on the `write(char[] cbuf, int offset,
int length)` overload and correct null-handling in `append(CharSequence
csq, int start, int end)`.

## Requirements (target the `char[]` overload specifically, NOT
## `write(String, int, int)` - that overload delegates to
## `StringBuilder.append` and is already fully covered by existing tests)
- `write(char[] cbuf, int offset, int length)` must throw
  `IndexOutOfBoundsException` when `offset < 0`, or `offset > cbuf.length`,
  or `length < 0`, or `offset + length > cbuf.length`.
- `write(char[] cbuf, int offset, int length)` with `length == 0` must
  return immediately without throwing and without appending anything, even
  if `offset` would otherwise be out of range.
- `append(CharSequence csq, int start, int end)` must treat a `null`
  CharSequence as the literal string `"null"` before taking the
  `start`/`end` subsequence (e.g. `append(null, 0, 4)` should append
  `"null"`).

## Out of scope
- The `write(String, int, int)` overload (already fully tested).
- Thread-safety guarantees beyond what the internal `StringBuilder` lock
  already provides.

