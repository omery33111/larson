


export interface Trade {
    id: number;
    executed_at: string;
    opened_at: string | null;
    symbol: string;
    account_id: string;
    source_platform: string;
    source_timezone: string;
    outcome: string;
    direction: string;
    quantity: number | null;
    entry_price: number | null;
    exit_price: number | null;
    pnl: number | null;
    points: number | null;
    fees: number | null;
    r_multiple: number | null;
    stop_loss: number | null;
    take_profit: number | null;
    duration_seconds: number | null;
    orders_count: number | null;
    setups: string;
    tags: string;
    mistakes: string;
    notes: string;
    rating: number | null;
    screenshot_url: string;
}


export interface TradeFile {
    id: number;
    original_name: string;
    source_platform: string;
    uploaded_at: string;
    row_count: number;
    imported_count: number;
    skipped_count: number;
    confirmed: boolean;
}


export interface SkippedRow {
    row: number;
    reason: string;
}


export interface EnrichmentField {
    key: string;
    label: string;
    coverage?: number;
    total?: number;
}


export interface IngestionReport {
    total_rows: number;
    parsed: number;
    skipped_count: number;
    skipped_rows: SkippedRow[];
    new_count: number;
    duplicate_count: number;
    accounts: string[];
    symbols: string[];
    date_from: string | null;
    date_to: string | null;
    source_timezone: string;
    outcome_from_file: number;
    outcome_derived: number;

    // True when the file's format was unknown and Larson identified the columns himself. The
    // confirmation screen says so out loud, because a guess deserves a look before a yes.
    mapped_by_model?: boolean;
    breakeven_threshold: number;
    enrichment_found: EnrichmentField[];
    enrichment_empty: EnrichmentField[];
    enrichment_missing: EnrichmentField[];
    unmapped_columns: string[];
}


export interface SampleTrade {
    executed_at: string;
    symbol: string;
    outcome: string;
    direction: string;
    quantity: number | null;
    entry_price: number | null;
    exit_price: number | null;
    pnl: number | null;
    setups: string;
    mistakes: string;
}


export interface UploadPreview {
    trade_file: TradeFile;
    report: IngestionReport;
    sample: SampleTrade[];
}


export interface ConfirmResult {
    success: boolean;
    imported: number;
    duplicates: number;
    invalid_rows: number;
    total_trades: number;
}


export interface TradesSummary {
    last_updated?: string | null;
    total_trades: number;
    date_from?: string;
    date_to?: string;
    symbols?: string[];
    accounts?: string[];
    files?: TradeFile[];
}


export interface TradesState {
    preview: UploadPreview | null;
    confirmResult: ConfirmResult | null;
    summary: TradesSummary;
    trades: Trade[];

    isUploading: boolean;
    isConfirming: boolean;
    isLoading: boolean;

    isConfirmOpen: boolean;

    // The resume dialog, and the second gate inside it. Deleting everything is irreversible,
    // so arming that button is a state of its own rather than a click away from the trash.
    // Bumped whenever the resume actually changes - a file confirmed in, or the whole thing
    // deleted. Screens that render statistics derived from it watch this number instead of
    // being told about it, so nothing has to know who is on screen when it happens.
    resumeVersion: number;

    isResumeOpen: boolean;
    isArmed: boolean;
    isDeleting: boolean;

    message: string;
}
