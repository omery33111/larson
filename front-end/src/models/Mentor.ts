import { ChatMessage } from './Chat';


/** What Larson currently knows, and how stale it is. */
export interface ResumeState {
    total_trades: number;
    last_trade: string | null;

    // Days between the last trade he knows about and now. This is the gap the mentor exists
    // to close, and it is what the nudge in the navbar counts.
    days_since: number | null;
}


/**
 * A file already in the resume, still waiting for the trader to press send.
 *
 * It is server state, not screen state. He may attach a file, get pulled away, close the tab
 * and come back tomorrow on another machine - the trades are saved either way, and what is
 * still owed is the conversation about them.
 */
export interface PendingFile {
    id: number;
    original_name: string;
    imported_count: number;
    duplicate_count: number;
}


import { RuleCoverage, RuleKind, TraderRule } from "./Rule";


export interface MentorState {
    messages: ChatMessage[];
    resume: ResumeState;

    streamingText: string;
    streamingMessageId: number | null;

    // Arrives with the first event, so the avatar carries the verdict while the answer is
    // still being written rather than only once it has landed.
    streamingVerdict: 'kept' | 'broken' | '';
    isStreaming: boolean;
    isWaiting: boolean;

    draft: string;

    // The mentor opened the ingestion dialog, so the confirmation that follows is his to act
    // on. Without it, confirming a file on the upload screen would fire a debrief here.
    isAwaitingConfirm: boolean;

    // The confirmed file sitting on the composer. It is not sent until he says so: he may
    // well want to write the note after choosing the file rather than before it.
    pendingFile: PendingFile | null;

    isDragging: boolean;
    isLoading: boolean;

    message: string;

    // **The rules he set for himself.** UI state lives in the slice like everywhere else in
    // this project - the panel opens on a dispatch and renders itself from the store, with
    // no props threaded down and no useState in the parent.
    rules: TraderRule[];

    // Set once, by the save that produced it, and cleared when the panel closes: it answers
    // "can my trades even answer this", which is a question about the rule he just wrote and
    // not a standing property of the screen.
    ruleCoverage: (RuleCoverage & { id: number; lookingFor: string }) | null;
    ruleKinds: RuleKind[];
    isRulesOpen: boolean;
    isRulesLoading: boolean;
}
