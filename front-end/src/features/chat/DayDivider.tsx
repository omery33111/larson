/**
 * The date, in the middle of the thread, each time the day turns over.
 *
 * **The mentor thread is one conversation that never ends** - it is the whole point of that
 * screen - so without this it is a wall of answers with nothing saying which session was
 * which. "What did he tell me after Tuesday" had no way of being asked.
 *
 * **A day and never a time**, which is the decision worth recording. Instagram prints the
 * hour because it groups by burst of activity; here the unit is a trading day, because the
 * thing being recorded is how a day went. An hour in the middle of the thread would be a
 * second timestamp competing with the one that matters.
 *
 * Read in his own browser's clock rather than a zone chosen here. Trade times render in the
 * file's `source_timezone` because they describe a market; a message describes **when he
 * wrote it**, and that is the clock he is looking at.
 */

const DAY = 86_400_000;


/** Whether this message opens a day the one before it did not. The first always does. */
export const startsANewDay = (current: string, previous?: string | null) => {
  if (!previous) return true;

  return new Date(current).toDateString() !== new Date(previous).toDateString();
};


/**
 * **Four shapes, and each one is the shortest thing that is still unambiguous.** "Tuesday"
 * is instant inside the last week and meaningless outside it - a week on it could be either
 * Tuesday - so past that it becomes a date, and past a year it carries the year.
 */
const label = (iso: string) => {
  const at = new Date(iso);
  const midnight = (d: Date) => new Date(d).setHours(0, 0, 0, 0);
  const days = Math.round((midnight(new Date()) - midnight(at)) / DAY);

  if (days === 0) return 'היום';
  if (days === 1) return 'אתמול';

  if (days < 7 && days > 0) {
    return at.toLocaleDateString('he-IL', { weekday: 'long' });
  }

  const sameYear = at.getFullYear() === new Date().getFullYear();

  return at.toLocaleDateString('he-IL',
    sameYear ? { day: 'numeric', month: 'long' }
             : { day: 'numeric', month: 'long', year: 'numeric' });
};


const DayDivider = ({ at }: { at: string }) => (
  // `separator` rather than a heading: it divides the thread, it does not title a section,
  // and a screen reader announcing it as a heading would promise structure that is not there.
  <div className="chat-day" role="separator" aria-label={label(at)}>
    <span className="chat-day-label">{label(at)}</span>
  </div>
);

export default DayDivider
