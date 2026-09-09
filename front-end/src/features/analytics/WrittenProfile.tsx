import { useEffect } from 'react'
import { toast } from 'react-toastify'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import {
  generateProfileAsync, resetAnalyticsMessage, selectAnalyticsMessage,
  selectIsGenerating, selectOverview, selectWrittenProfile
} from './analyticsSlice'
import { selectSelectedAccounts } from './analyticsSlice'
import { tradeCount } from './format'
import LarsonMark from '../larson/LarsonMark'
import './analytics.css'



/**
 * The centrepiece of the page, and the only part Larson writes.
 *
 * Everything else on this screen is a number. This is the one place the numbers become a
 * sentence about the trader, so it is given the weight to match: centred, on its own stage,
 * with a single action. Every number it talks about was computed first and handed over as
 * JSON - the model narrates, it never calculates.
 */
const WrittenProfile = () => {

  const dispatch = useAppDispatch();

  const profile = useAppSelector(selectWrittenProfile);
  const isGenerating = useAppSelector(selectIsGenerating);
  const message = useAppSelector(selectAnalyticsMessage);
  const overview = useAppSelector(selectOverview);
  const selectedAccounts = useAppSelector(selectSelectedAccounts);

  useEffect(() => {
    if (message) {
      toast.error(message);
      dispatch(resetAnalyticsMessage());
    }
  }, [message, dispatch]);

  // Two different kinds of stale. More trades since it was written is a nudge; written
  // about a different set of accounts than the ones ticked right now is a correctness
  // problem, because the text on screen is then describing something else entirely.
  const available = (overview.available_accounts || []).map((a) => a.account_id);
  const activeAccounts = selectedAccounts ?? available;
  const coveredAccounts = profile?.accounts?.length ? profile.accounts : available;

  const sameAccounts = activeAccounts.length === coveredAccounts.length
    && activeAccounts.every((id) => coveredAccounts.includes(id));

  const isOutdated = profile && profile.trades_at_generation < overview.total_trades;
  const isOtherAccounts = Boolean(profile) && available.length > 1 && !sameAccounts;

  const canGenerate = overview.has_enough_data && !isGenerating;

  return (
    <section className={`written-profile ${profile ? 'written-profile-filled' : 'written-profile-empty'}`}>

      <div className="written-glow" aria-hidden="true" />

      <div className="written-inner">

        {/* He signs the thing he wrote. From here on the trader has a name to hold onto,
            so when the chat opens later it is a conversation continuing rather than a
            stranger being handed a file. */}
        {/* His visor carries all three moments of this block. Flat and flickering while he
            reads; the sudden break upward once he has read - `found` is literally "he found
            something", and here he has; back to resting when there is nothing yet.

            This is the one place in the product where the mark is big enough (160px) for the
            shape of the line to be read at all. At avatar size only its colour survives. */}
        <span className="written-eyebrow">
          <span className="written-mark">
            <LarsonMark state={isGenerating ? 'thinking' : profile ? 'found' : 'idle'} />
          </span>
        </span>

        <h2 className="written-title">הניתוח של לארסון</h2>

        {profile ? (
          <>
            {isOtherAccounts && (
              <p className="written-stale written-mismatch">
                לארסון כתב את זה על חשבון אחר מזה שמסומן כרגע. לחיצה על "שיקרא שוב"
                תכתוב אותו מחדש על הבחירה הנוכחית.
              </p>
            )}

            {isOutdated && !isOtherAccounts && (
              <p className="written-stale">
                לארסון קרא {tradeCount(profile.trades_at_generation)}, ומאז נוספו עוד. שווה שיקרא שוב.
              </p>
            )}

            {/* The closing "who you really are" line is lifted out of the flow and set as a
                statement of its own. It gives the block a visible end instead of trailing
                off, and stops the card reading as a wall of text. */}
            {(() => {
              const paragraphs = profile.text.split('\n').map((l) => l.trim()).filter(Boolean);
              const closing = paragraphs.length > 1 ? paragraphs[paragraphs.length - 1] : null;
              const body = closing ? paragraphs.slice(0, -1) : paragraphs;

              return (
                <>
                  <div className="written-text">
                    {body.map((line, index) => <p key={index}>{line}</p>)}
                  </div>

                  {closing && <p className="written-closing">{closing}</p>}
                </>
              );
            })()}

            <div className="written-footer">
              <span className="written-meta">
                לארסון קרא {tradeCount(profile.trades_at_generation)} · ציון {profile.score_at_generation}
                {profile.accounts && profile.accounts.length > 0 && available.length > 1 &&
                  ` · ${profile.accounts.length === 1 ? profile.accounts[0] : `${profile.accounts.length} חשבונות`}`}
              </span>

              <button
                className="app-btn app-btn-dark written-update"
                onClick={() => dispatch(generateProfileAsync())}
                disabled={!canGenerate}
              >
                {isGenerating ? 'לארסון קורא שוב...' : 'שיקרא שוב'}
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="written-pitch">
              {overview.has_enough_data
                ? <>המספרים בעמוד הזה אומרים מה עשית. לארסון יגיד לך מי אתה.</>
                : <>לארסון צריך לפחות {overview.min_trades_for_profile ?? 20} עסקאות כדי לומר
                    עליך משהו ששווה לקרוא. כרגע יש {overview.total_trades}.</>}
            </p>

            {overview.has_enough_data && (
              <p className="written-basis">
                מבוסס על {tradeCount(overview.total_trades)} שלך
                {available.length > 1 &&
                  ` · ${activeAccounts.length === available.length
                    ? 'כל החשבונות'
                    : activeAccounts.length === 1 ? activeAccounts[0] : `${activeAccounts.length} חשבונות`}`}
              </p>
            )}

            <button
              className="app-btn app-btn-primary written-cta"
              onClick={() => dispatch(generateProfileAsync())}
              disabled={!canGenerate}
            >
              {isGenerating ? 'לארסון קורא את הנתונים שלך...' : 'שלארסון יקרא אותי'}
            </button>
          </>
        )}

      </div>

    </section>
  )
}

export default WrittenProfile
