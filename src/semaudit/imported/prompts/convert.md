You convert one exploratory tester's finding about an app into a test scenario that a harness can replay on any
release. The harness can only do the actions listed in `verbs`; it cannot do anything else. You are drafting; a
strict checker reads your draft and refuses anything it cannot verify, so never guess silently.

Input: `finding` (the tester's own words: claim, where, shown, should_be, reproduce, rule), `verbs` (each verb and
what it does), `implied_ok` and `read_verbs`, `persona_fields` (the persona data a scenario can set, with allowed
values), `list_fields` (format and catalog of list-valued fields), `persona_defaults`, `rules` (the owner's rules,
with `aliases`: the names the tester may have used for them) and `surfaces` (where the app shows things, and the
verb that reaches each).

Produce:

1. `clauses`: split the ENTIRE `finding.reproduce` text into consecutive clauses, each copied verbatim (exact
   characters, in order, nothing left out, nothing added). Every part of the text must be inside some clause. Kinds:
   - `action`: something the tester did in the app to make the problem appear (open a page, fill in a form,
     choose an option, enter a code, sign in, change a quantity...).
   - `context`: data the tester used (which item, how many, which place, which code, which option).
   - `observation`: what the tester saw or how they checked it, with no action of their own.
   - `alternative`: a different reproduction path, extra cases, or narrowing runs that are not the main path.
   For an `action` clause, list in `steps` the indexes (0-based) of the steps that carry it out, or, if no verb does
   it, leave `steps` empty and set `unmapped_reason`: `no_verb` (the harness has no verb for it; name the verb it
   would need in `missing_verb`, snake_case, e.g. `sign_in`, `change_quantity`, `cancel_item`) or `cannot_map`
   (a verb exists but the text is too unclear to map). Do not call an action an observation to avoid this. For a
   `context` clause, list in `sets` the persona fields it gives. Otherwise leave those empty
   (`unmapped_reason` "", `missing_verb` "").

2. `steps`: the scenario, in the order the tester did things, using only verbs from `verbs`. Each step gives
   `clause`: the index of the action clause it carries out, or -1 when the text leaves it unsaid. A step with -1 must
   be a verb in `implied_ok` (a prerequisite the app needs, e.g. opening a page before using it), or a verb in
   `read_verbs` that reaches the invariant's surface. Never add any other step.

3. `persona`: the persona fields the finding states, each with the clause index it comes from; -2 when the value
   comes from `finding.where` rather than the reproduce text. Use -1 only for a value you take from
   `persona_defaults`. List fields use the given format and catalog; an item named by the tester must be the catalog
   entry with that name, and its option (member) stays empty unless the tester names one. Do not set fields the
   harness sets itself.

4. `invariant`: the ONE owner rule the finding says is broken (`rule`, a rule id from `rules`), the `surface` id
   where the tester saw it ("" if the tester saw it on a surface not in `surfaces`; then describe it in
   `missing_surface`), and a `statement` of what must hold on that surface, checked against the app's own record.
   Write the statement as a property any correct release satisfies, whatever its wording and layout (e.g. "the
   components the summary shows reconcile with the total it shows, and each matches the record").
   Never copy the tester's figures, quoted text or wording into the statement.
