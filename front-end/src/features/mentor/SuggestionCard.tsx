import { FiCheck, FiX } from 'react-icons/fi'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import { RuleSuggestion } from '../../models/Rule'
import { acceptSuggestionAsync, dismissSuggestionAsync, selectMentorIsStreaming } from './mentorSlice'
import './mentor.css'



/**
 * The one question Larson asks under a debrief.
 *
 * **The server asks it, in his voice.** Python found the condition, computed the figure and
 * composed the card; the model never sees it and cannot press anything. That is not a
 * detail - "the model has no tools" is the whole reason an injected instruction in a trade
 * file cannot reach anybody's data, and a feature that let the model create rules would
 * have ended that argument.
 *
 * **It sits under a finished answer and never beside a streaming one.** Asking him to
 * commit while he is still reading why is asking before he has heard the reason.
 *
 * Two shapes, and the second is the one worth having. Any analytics product can propose a
 * rule from a losing bucket; **telling a trader he has outgrown one is what a mentor does**,
 * and nothing else in this product gets to say that.
 */


const SuggestionCard = ({ messageId, card }: { messageId: number, card: RuleSuggestion }) => {

  const dispatch = useAppDispatch();
  const isStreaming = useAppSelector(selectMentorIsStreaming);

  const retiring = card.action === 'retire';

  return (
    // **Inside a `chat-turn`, with an empty avatar slot.** Measured on the live page, the
    // card was 328px wider than the answer above it and three pixels below it - a panel
    // laid across the thread rather than something the answer is holding out. Borrowing the
    // row the answer already uses keeps the avatar's width in one place: hard-coding 46px
    // here would be a second copy of it, and the two would drift the first time it changes.
    <div className="chat-turn suggestion-turn">
      <span className="chat-avatar suggestion-spacer" aria-hidden="true" />

      <div className={`suggestion ${retiring ? 'suggestion-retire' : ''}`}>

        <p className="suggestion-title">{card.title}</p>
        <p className="suggestion-detail">{card.detail}</p>

        <div className="suggestion-actions">
          <button type="button" className="app-btn app-btn-primary suggestion-yes"
                  disabled={isStreaming}
                  onClick={() => dispatch(acceptSuggestionAsync(messageId))}>
            <FiCheck /> {card.accept}
          </button>

          {/* **A no is remembered for good.** The condition behind a suggestion is usually
              still true next week, so without that the same card returns every debrief
              until he gives in or stops reading them - which is the failure mode that
              kills features like this one. */}
          <button type="button" className="suggestion-no"
                  disabled={isStreaming}
                  onClick={() => dispatch(dismissSuggestionAsync(messageId))}>
            <FiX /> {card.decline}
          </button>
        </div>

      </div>
    </div>
  );
};


export default SuggestionCard
