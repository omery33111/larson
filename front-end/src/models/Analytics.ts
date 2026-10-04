

export interface ScorePillar {
    key: string;
    label: string;
    value: number;
    weight: number;
    detail: string;
}


export interface Score {
    total: number;
    grade: string;
    pillars: ScorePillar[];
}


export interface CoreMetrics {
    net_pnl: number;
    gross_profit: number;
    gross_loss: number;
    wins: number;
    losses: number;
    breakeven: number;
    win_rate: number;
    profit_factor: number | null;
    avg_win: number;
    avg_loss: number;
    win_loss_ratio: number | null;
    expectancy: number;
    largest_win: number;
    largest_loss: number;
    max_drawdown: number;
    avg_r: number | null;
    r_coverage: number;
}


export interface DailyMetrics {
    trading_days: number;
    green_days: number;
    red_days: number;
    flat_days: number;
    green_day_rate: number;
    avg_green_day: number;
    avg_red_day: number;
    best_day: number;
    worst_day: number;
    avg_trades_per_day: number;
    max_trades_in_a_day: number;
    daily_stdev: number;
}


export interface Streaks {
    longest_win_streak: number;
    longest_loss_streak: number;
    current_streak: number;
    current_streak_kind: string;
}


export interface GroupStat {
    key: string | number;
    /** A readable name for the group when one exists - "NQ" becomes the index name. */
    label?: string | null;
    trades: number;
    net_pnl: number;
    expectancy: number;
    win_rate: number;
    profit_factor: number | null;
    is_significant: boolean;
}


export interface Breakdowns {
    by_hour: GroupStat[];
    by_weekday: GroupStat[];
    by_symbol: GroupStat[];
    by_direction: GroupStat[];
    by_setup: GroupStat[];
    by_tag: GroupStat[];
    by_mistake: GroupStat[];
    by_duration: GroupStat[];
}


export interface Finding {
    key: string;
    title: string;
    detail: string;
    impact: number;
    evidence: string;
}


export interface WrittenProfile {
    text: string;
    generated_at: string;
    trades_at_generation: number;
    score_at_generation: number;
    accounts: string[];
}


export interface AccountSummary {
    account_id: string;
    label: string;
    trades: number;
    net_pnl: number;
    last_traded: string;
}


// ------------------------- ALONG THE TIME AXIS ------------------------- //
//
// The keys are Hebrew because the engine writes them for the model as well as for the screen,
// and one set of names means the sentence the trader reads and the sentence Larson reads
// cannot drift apart. Declared rather than cast around: `as any` on the one block the whole
// card renders would mean a rename in python breaks the screen silently.

export interface PeriodWindow {
    'עסקאות': number;
    'רווח_נקי': string;
    'תוחלת': string;
    'אחוז_הצלחה': string;
}

export interface PeriodMonth extends PeriodWindow {
    'חודש': string;
}

export interface PeriodNote {
    detail: string;
}

export interface Periods {
    available: boolean;
    reason?: string;
    'חודשים'?: PeriodMonth[];
    'השוואה_אחרונה'?: { available: boolean; 'פסיקה'?: string;[key: string]: unknown };
    'חצי_ראשון_מול_שני'?: { available: boolean; 'פסיקה'?: string;[key: string]: unknown };
    'מגמה'?: { available: boolean; 'כיוון'?: string; detail?: string };
    'שיאים'?: ({ 'שיא': string } & PeriodNote)[];
    'הדראודאון_הגדול'?: { available: boolean; detail?: string };
    'נדידה'?: ({ 'מה': string } & PeriodNote)[];
    'מה_הפסקת'?: ({ 'מה': string } & PeriodNote)[];
}


export interface AnalyticsOverview {
    total_trades: number;
    has_enough_data: boolean;
    min_trades_for_profile?: number;
    timezone?: string;
    currency?: string;
    date_from?: string;
    date_to?: string;
    accounts?: string[];
    core?: CoreMetrics;
    daily?: DailyMetrics;
    streaks?: Streaks;
    behaviour?: any;
    breakdowns?: Breakdowns;
    score?: Score;
    strengths?: Finding[];
    leaks?: Finding[];
    profile?: WrittenProfile | null;
    available_accounts?: AccountSummary[];
    selected_accounts?: string[];

    periods?: Periods;
}


export interface AnalyticsState {
    overview: AnalyticsOverview;

    isLoading: boolean;
    isGenerating: boolean;

    isMetricsOpen: boolean;

    // null means "every account", which is also the state before anything is chosen.
    selectedAccounts: string[] | null;

    message: string;
}
