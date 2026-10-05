// ------------------------- THE RULES HE SETS FOR HIMSELF ------------------------- //
//
// **A rule in his own words comes first; the structured kinds behind it are examples.**
// "Only enter when delta is high and there is an IFVG" is what a plan actually sounds like,
// and "do not enter before 10:00" is one narrow case of that.
//
// His sentence is still judged by a loop and never by the model. It is interpreted **once,
// when he saves it**, into terms stored on the row, and every check after that is python
// comparing strings - so the trade that broke it gets named by date and by time, exactly
// like the hour rule.

export interface TraderRule {
    id: number;
    kind: string;
    /** Minutes from midnight for the two time rules; the unit of the kind for the rest. */
    number: number | null;
    // His sentence, exactly as typed. Only the free-text kind carries one, and our reading
    // of it deliberately never comes back down - he would start editing the paraphrase.
    text: string;
    /** Only the free-text kind carries these, and only so the editor can render them. */
    terms?: RuleTerms | null;
    looking_for?: string;
    /** **How many of his trades this rule's words currently find.** A number instead of a
     *  paragraph: `0` says "this finds nothing" faster than any sentence explaining that it
     *  might. Null when the server did not compute it. */
    matched?: number | null;
    is_active: boolean;
    created_at: string;
}

/** How many of his trades can answer the rule he just saved, out of how many he has.
 *  **The number that stops the feature from lying**: without it a rule reports "kept" over
 *  a year of trades that recorded nothing at all. */
export interface RuleCoverage {
    /** Trades carrying any text at all - these are the ones the rule can be judged against. */
    answerable: number;
    total: number;
    /** **Trades where a term of this rule actually appears.** Zero means the engine has
     *  never seen this concept in his record, which almost always means it cannot see it
     *  at all - a news calendar, the VIX, the spread. Every tagged trade would then fail
     *  the requirement, and telling him he broke a rule he kept is worse than silence. */
    matched: number;
}

/** `require` is an AND of groups; each group is an OR of spellings. Flat enough to edit as
 *  rows of chips, which is the only reason it can be put in front of a trader at all. */
export interface RuleTerms {
    require: string[][];
    forbid: string[];
}

/** What a set of terms would find right now, per term, over his own record. **The thing
 *  that turns editing from guessing into feedback** - a term showing 0 is visibly dead. */
export interface RulePreview {
    per_term: Record<string, number>;
    coverage: RuleCoverage;
    labels: string[];
}

export interface RuleKind {
    kind: string;
    label: string;
}

export interface EmailPreferences {
    weekly_digest: boolean;
    product_news: boolean;
}
