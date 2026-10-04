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
    number: number | null;
    setups: string;
    // His sentence, exactly as typed. Only the free-text kind carries one, and our reading
    // of it deliberately never comes back down - he would start editing the paraphrase.
    text: string;
    is_active: boolean;
    created_at: string;
}

/** How many of his trades can answer the rule he just saved, out of how many he has.
 *  **The number that stops the feature from lying**: without it a rule reports "kept" over
 *  a year of trades that recorded nothing at all. */
export interface RuleCoverage {
    answerable: number;
    total: number;
}

export interface RuleKind {
    kind: string;
    label: string;
}

export interface EmailPreferences {
    weekly_digest: boolean;
    product_news: boolean;
}
