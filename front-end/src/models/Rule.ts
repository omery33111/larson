// ------------------------- THE RULES HE SETS FOR HIMSELF ------------------------- //
//
// **Structured and never free text**, which is the whole reason the debrief can judge them.
// Every number in this product is computed in python and only narrated by the model; a rule
// typed as a sentence could only be judged by the model, and compliance would become an
// opinion. A kind and a number can be judged by a loop - which is how the trade that broke it
// gets named by date and by time.

export interface TraderRule {
    id: number;
    kind: string;
    number: number | null;
    setups: string;
    is_active: boolean;
    created_at: string;
}

export interface RuleKind {
    kind: string;
    label: string;
}

export interface EmailPreferences {
    weekly_digest: boolean;
    product_news: boolean;
}
