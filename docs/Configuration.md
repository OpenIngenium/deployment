# Configuration Reference

## Command String Format

`CMD_STRING_FORMAT` (in `ing_envs.sh`) controls how a command's STEM and ARGS
are assembled into a single command string. It is rendered client-side by
`src/client/src/modules/elements/executable/cmd/cmd-string-format.js` from
`window.cmdStringFormat` (populated via `templateLocals.js` -> `head.ejs`).

### Tokens

| Token | Description |
|---|---|
| `{{STEM}}` | The command stem/name. |
| `{{PRE_ARGS}}...{{/PRE_ARGS}}` | Renders only when at least one argument exists. Use to prefix the argument list (e.g. with a separator). |
| `{{POST_ARGS}}...{{/POST_ARGS}}` | Renders only when at least one argument exists. Use to suffix the argument list. |
| `{{#ARGS}}...{{/ARGS}}` | Repeated block, once per argument. |
| `{{ARG_NAME}}` | Name of the current argument (only valid inside `{{#ARGS}}...{{/ARGS}}`). |
| `{{ARG_VALUE}}` | Value of the current argument (only valid inside `{{#ARGS}}...{{/ARGS}}`). |
| `{{SEP}}...{{/SEP}}` | Renders BETWEEN arguments only (i.e. not after the last argument). Use inside `{{#ARGS}}...{{/ARGS}}` to join argument values. |

### Examples

For `STEM=PWR_CTRL` with args `SUBSYSTEM=SSPA` and `STATE=ON`:

- Default:
  ```
  {{STEM}}{{PRE_ARGS}},{{/PRE_ARGS}}{{#ARGS}}{{ARG_VALUE}}{{SEP}},{{/SEP}}{{/ARGS}}
  ```
  Result: `PWR_CTRL,SSPA,ON`
  (With no args: `PWR_CTRL` - the `{{PRE_ARGS}}` comma is skipped since there are no arguments.)

- Named args, space-separated:
  ```
  {{STEM}}{{#ARGS}} {{ARG_NAME}}={{ARG_VALUE}}{{/ARGS}}
  ```
  Result: `PWR_CTRL SUBSYSTEM=SSPA STATE=ON`

### Round-trip (re-parse) caveats

If the UI needs to re-parse a typed/pasted command string back into STEM +
ARGS, the chosen format must be unambiguous:

- Prefer a consistent, fixed separator (e.g. `,` or a single space) between
  the STEM and the first argument, and between arguments, so the parser can
  reliably split the string.
- Avoid formats where `{{ARG_VALUE}}` values could themselves contain the
  separator character, unless the parser is aware of quoting/escaping rules.
- If using `{{ARG_NAME}}={{ARG_VALUE}}` pairs, ensure argument names never
  contain the separator or `=` characters.
- Empty/optional arguments should be handled consistently with how
  `{{PRE_ARGS}}`/`{{POST_ARGS}}`/`{{SEP}}` behave when zero or one argument
  is present, otherwise re-parsing may produce incorrect results.

### Setting the value

`CMD_STRING_FORMAT` is set in each instance's `ing_envs.sh`
(see `project_instance_template/ing_envs.sh`) and can also be configured
interactively via the `setup_instance.py` wizard. Keep the value quoted so
that `#` characters are not treated as a dotenv comment.
