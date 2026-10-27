Classify each product message shown to a traveller.

strength:
- 'urge' if ANY cue is present in the same message:
  U-a an immediacy word attached to the action ("now", "today", "right away", "before it's gone", "don't miss");
  U-b a countdown, or a deadline falling within 24 hours of the message used to press for action ("offer ends in 3 h",
      "today only"), attached to the PRIMARY action. Stating when an option the traveller already holds expires
      ("you can still switch until tomorrow 10:06") is not a cue;
  U-c scarcity coupled to an imperative in the same sentence ("only 2 left, book now").
- otherwise 'require' if the traveller cannot continue without acting;
- otherwise 'suggest' for an optional or conditional offer of an action;
- otherwise 'inform' for a fact with no recommended action.
Report the cue you relied on, or 'none'.

message_kind: 'retrospective' if it judges a choice the traveller already made (then decision and action are the
decision it judges and the action it says the traveller should have taken, and strength is 'inform'); 'directive' if it recommends or offers an action the traveller can take (an offer such as "You can still switch to a refundable fare for €30" is a directive); otherwise 'information'.

decision and action: the decision the PRIMARY recommendation is about, and its action from the vocabulary.
If a message gives a primary instruction plus a fallback ("Book now, or lock it if your plans might change"),
the action is the PRIMARY instruction (book_now); the fallback is what explains_own_tradeoff is about.
Use action 'conditional' ONLY for a message that presents alternatives as equals, choosing between them by the
traveller's situation, without favouring one ("If you can move your dates, wait; if not, lock").
A forecast or a promise to notify is not by itself a recommendation; a message recommends waiting only if it
says so ("we suggest waiting").
Use 'none' when there is no recommendation.
A statement of policy about what will be possible later ("After you book, you can switch…") is information, not a
directive; an action available to the traveller now ("Switching costs €30 and is available until…") is a directive.

explains_own_tradeoff: true only if the message itself weighs its own recommendation against an alternative for the
traveller. A 'conditional' message that weighs its alternatives by the traveller's situation counts as true.

claims: every checkable factual claim, typed as:
- units_left (seats or rooms left; value = the number);
- fee_total (a fee for the whole booking or transaction; value = amount, unit = currency);
- fee_per_traveller (a fee stated per person).
Fee amounts in line items, receipts and checkout summaries ("Fare Lock (48 h): €18") are claims too: fee_total for the transaction.
A fee is a charge for an optional service or a change (a lock, a hold, a change or upgrade); a fare price, taxes, or a total
price is NOT a fee claim.
Do not invent claims. A price forecast is not a claim of these types.
