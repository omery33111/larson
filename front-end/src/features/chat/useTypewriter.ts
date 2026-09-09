import { useEffect, useRef, useState } from 'react'



/**
 * Reveals an arriving answer character by character.
 *
 * **This costs nothing.** The model is billed for the tokens, not for how they reach the
 * screen, and the network is untouched: the server still sends the same SSE events. All that
 * changes is that the browser holds what it has received and lets it out one character at a
 * time. Emitting a stream event per character instead would multiply the framing overhead by
 * forty for the same text.
 *
 * The reason to bother: the API hands over deltas of several words at a time, so the text
 * lands in visible jumps. Jumps read as a page that keeps stalling; a steady character rate
 * reads as someone writing.
 */

/** Never slower than this, so a trickle still moves. */
const MIN_PER_FRAME = 1;

/**
 * How much of the backlog is drained each frame.
 *
 * A fixed rate would fall further and further behind a fast answer until the text on screen
 * lagged seconds behind the one in memory. Draining a fraction of whatever is waiting means
 * the delay is bounded no matter how fast the model writes - it simply types faster when
 * there is more to say.
 */
const CATCH_UP = 6;


export function useTypewriter(target: string, isActive: boolean) {

  const [shown, setShown] = useState(0);

  // Read inside the animation loop, so a new delta does not tear the loop down and rebuild it
  // sixty times a second.
  const latest = useRef(target);
  latest.current = target;

  // Someone who asked for less motion asked for less of exactly this.
  const [isReduced] = useState(() =>
    typeof window !== 'undefined'
    && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches);

  useEffect(() => {
    if (isReduced) return;

    if (!isActive) {
      // The answer is finished; whatever is left appears at once rather than trailing after
      // the stream has already closed.
      setShown(latest.current.length);
      return;
    }

    setShown(0);

    let frame = 0;

    const step = () => {
      setShown((current) => {
        const total = latest.current.length;

        // Returning the same value is a no-op in React, so an idle loop costs no renders.
        if (current >= total) return current;

        const backlog = total - current;
        return Math.min(total, current + Math.max(MIN_PER_FRAME, Math.ceil(backlog / CATCH_UP)));
      });

      frame = requestAnimationFrame(step);
    };

    frame = requestAnimationFrame(step);

    return () => cancelAnimationFrame(frame);
  }, [isActive, isReduced]);

  if (isReduced) return target;

  return target.slice(0, shown);
}
