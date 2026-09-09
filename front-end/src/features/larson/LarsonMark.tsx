import { useId } from 'react'
import {
  HAIR_BRIGHT, HAIR_CONTOUR_DARK, HAIR_CONTOUR_FADE, HAIR_DARK, HAIR_HIGHLIGHTS, HAIR_LIGHT,
  HAIR_MASS, HAIR_STRAND_TIERS,
} from './hair'
import './larson.css'



/**
 * Larson himself, as a component rather than an <img>.
 *
 * He has no eyes, he has a chart - and that chart is the whole reason this shape was chosen
 * over the other two designs: he changes expression without changing form. That is what
 * lets a streaming answer show that something is happening without a spinner sitting next
 * to a static picture.
 *
 * Everything except the polyline is identical between states. The line is drawn inside a
 * clipPath of the visor rectangle, so no state can push it outside the glass.
 *
 * The two shoulder variants live here too rather than as their own SVG files. They are the
 * same figure with something added above or across it, and as separate files each one held
 * its own copy of the head, the hair and the visor - three copies to keep in agreement, and
 * the hair changed once and left two of them behind.
 */

export type LarsonState = 'idle' | 'thinking' | 'found' | 'success' | 'warning';

/** Plain, or one of the two shoulders in "the angel and the devil". */
export type LarsonVariant = 'plain' | 'angel' | 'devil';

type VisorState = {
  points: string;
  stroke: string;
  dot?: { cx: number; cy: number; r: number; fill: string };
};

const VISOR: Record<LarsonState, VisorState> = {
  idle: {
    points: '60,122 74,114 84,120 96,104 108,112 120,99 132,107 144,101',
    stroke: '#f0b90b',
    dot: { cx: 120, cy: 99, r: 5, fill: '#ffd34d' },
  },

  // Almost flat, and flickering. Nothing has been decided yet.
  thinking: {
    points: '58,112 74,110 86,114 98,110 110,114 122,110 134,114 146,111',
    stroke: '#b3860f',
  },

  // A sudden break upward at the end: he found something. Deliberately not the same as
  // success, which is a steady climb across the whole visor - something worked.
  found: {
    points: '58,124 76,122 90,123 104,119 116,103 128,95 146,89',
    stroke: '#f0b90b',
    dot: { cx: 146, cy: 89, r: 5.5, fill: '#ffd34d' },
  },

  success: {
    points: '58,126 74,121 88,115 102,111 116,102 130,98 144,89',
    // Brighter than the app's own green, because the visor glass is darker than any card
    // on screen and the line has to stay readable at 24px.
    stroke: '#35bd79',
    dot: { cx: 144, cy: 89, r: 5.5, fill: '#6ee7a0' },
  },

  warning: {
    points: '58,101 74,105 88,101 100,109 112,125 126,119 146,127',
    stroke: '#d1494e',
  },
};


/**
 * Where the figure sits in the 200-square.
 *
 * Both are derived from what is actually drawn rather than nudged by eye: the content runs
 * from the top of the hair to the bottom of the neck, and these centre that span. They move
 * whenever the hair does, which is why the numbers are odd ones.
 *
 * The two shoulders are scaled down, because at full size there is no room above his hair -
 * and that room is exactly what the halo and the horns need.
 */
const FRAME: Record<LarsonVariant, string> = {
  plain: 'translate(0 5.9)',
  angel: 'translate(15 26) scale(0.84)',
  devil: 'translate(15 26) scale(0.84)',
};

/**
 * Rooted on the forehead just above the visor, and drawn IN FRONT of the hair. A horn grows
 * out of the skull, so it has to cross the hair rather than hide behind it; a version that
 * sat behind read as decoration rather than anatomy.
 *
 * Wide at the base and sharply tapered - a first attempt made them long and slender and they
 * read as fox ears. Base width is what separates a horn from an ear, and these keep it at 20.
 *
 * **Both numbers here were wrong in a way that only showed on one side.** They are drawn in
 * the outer square, outside FRAME - and FRAME puts the figure's centre at 15 + 0.84 x 100 =
 * 99, not 100. Mirrored about 100, the right horn sat a full two units further from the head
 * than the left, which is exactly what it looked like. And the left horn's outer base corner
 * was 1.3 units OUTSIDE the head's own outline, so it floated off the skull instead of
 * growing out of it.
 *
 * So the base corners are now points on the head's own top corner arc - centre (78.8, 108.3),
 * radius 25.2 in this space - taken at 105 and 155 degrees and inset 1.5 so they bite into the
 * skull rather than balance on it. The right horn is the left one mirrored about 99.
 */
const HORNS = [
  'M57.4 98.3 C43 78 33 48 30 22 C42 46 60 70 72.7 85.4 Z',
  'M140.6 98.3 C155 78 165 48 168 22 C156 46 138 70 125.3 85.4 Z',
];


type Props = {
  state?: LarsonState;
  variant?: LarsonVariant;
  className?: string;
};


const LarsonMark = ({ state = 'idle', variant = 'plain', className = '' }: Props) => {

  // Several marks share a page - the navbar, the avatar on every answer. Without a unique
  // suffix they would all point at the first instance's gradients.
  const uid = useId().replace(/:/g, '');

  const visor = VISOR[state];

  const label = variant === 'angel' ? 'לארסון עם הילת מלאך'
    : variant === 'devil' ? 'לארסון עם קרני שטן'
    : 'לארסון';

  return (
    <svg
      className={`larson-figure larson-figure-${state} ${className}`}
      viewBox="0 0 200 200"
      role="img"
      aria-label={label}
    >
      <defs>
        {/* Brushed steel, lit across the form rather than down it. He used to be built out
            of the same near-black the theme's background is made of, which is why he
            disappeared into every dark surface he was placed on. */}
        <linearGradient id={`head-${uid}`} x1="0.18" y1="0" x2="0.82" y2="1">
          <stop offset="0" stopColor="#a6afbe" />
          <stop offset="0.30" stopColor="#77808f" />
          <stop offset="0.58" stopColor="#4e5563" />
          <stop offset="0.80" stopColor="#373e49" />
          <stop offset="1" stopColor="#4b5360" />
        </linearGradient>


        {/* A point light standing up and to the left, not a gradient running bottom to top.
            An axis running along the strands lights every one of them identically at every
            height and the mass reads as one curved surface. With the light crossing them,
            each lands on a different part of the falloff - which is what light on hair does.

            The falloff ends in gold, not in brown: a desaturated tan at the dark end reads
            as murky and kills the glow.

            All three tones are the same light moved along its own falloff, on the same
            axis - so none of them is a flat colour dropped over the hair. */}
        {[[`hair-${uid}`, HAIR_LIGHT], [`strand-${uid}`, HAIR_DARK],
          [`glow-${uid}`, HAIR_BRIGHT],
          [`edge-dark-${uid}`, HAIR_CONTOUR_DARK]].map(([id, stops]) => (
          <radialGradient key={id as string} id={id as string} gradientUnits="userSpaceOnUse"
            cx="52" cy="18" r="150" fx="46" fy="10">
            {(stops as string[]).map((color, i) => (
              <stop key={color} offset={['0', '.34', '.66', '1'][i]} stopColor={color} />
            ))}
          </radialGradient>
        ))}

        {variant === 'angel' && (
          // The only cold colour in the product, and it is allowed here precisely because
          // it is a halo.
          <linearGradient id={`halo-${uid}`} x1="0" y1="0" x2="1" y2="0">
            <stop offset="0" stopColor="#5fb9d9" />
            <stop offset=".5" stopColor="#bfeaf8" />
            <stop offset="1" stopColor="#5fb9d9" />
          </linearGradient>
        )}

        {variant === 'devil' && (
          // The product's own loss red, which is the point: this shoulder is the money
          // being burned.
          <linearGradient id={`horn-${uid}`} x1="0" y1="1" x2="0" y2="0">
            <stop offset="0" stopColor="#8e2b2f" />
            <stop offset=".55" stopColor="#d1494e" />
            <stop offset="1" stopColor="#f27272" />
          </linearGradient>
        )}

        <clipPath id={`visor-${uid}`}>
          <rect x="58" y="92" width="84" height="40" rx="18" />
        </clipPath>

        {/* The hair's own outline. The contour lines below are strokes, so half of each one
            falls outside the shape it draws; this guarantees not a thousandth of a unit of
            it can land outside the silhouette. */}
        <clipPath id={`mane-${uid}`}>
          <path d={HAIR_MASS} />
        </clipPath>

        {/* The contour fades out towards the centre of the mane rather than being cut off
            there. See HAIR_CONTOUR_FADE: the innermost strands are the finest and they
            converge, so outlining each of them crowds several hard lines into a pixel or two.
            Tone survives that; a hard line cannot. A clip would end every line on the same
            arc and read as a seam - a fade reads as the depth it actually is. */}
        <radialGradient id={`fade-${uid}`} gradientUnits="userSpaceOnUse"
          cx="100" cy={HAIR_CONTOUR_FADE.cy} r={HAIR_CONTOUR_FADE.r}>
          <stop offset="0" stopColor="#000" />
          <stop offset={HAIR_CONTOUR_FADE.core} stopColor="#000" />
          <stop offset="1" stopColor="#fff" />
        </radialGradient>

        <mask id={`edge-fade-${uid}`} maskUnits="userSpaceOnUse">
          <rect x="-50" y="-50" width="300" height="300" fill={`url(#fade-${uid})`} />
        </mask>
      </defs>

      {/* Behind the hair, so the tall locks cross it from in front. That overlap is the whole
          reason it reads as a ring floating above a head rather than as a hat brim. */}
      {variant === 'angel' && (
        <ellipse cx="100" cy="34" rx="50" ry="12" fill="none"
          stroke={`url(#halo-${uid})`} strokeWidth="7" />
      )}

      <g transform={FRAME[variant]}>
        {/* y 99, which is where the reference's pods land once the head is the right shape -
            and within a unit of where ours were drawn all along. The hair covers the top 8.7
            (left) and 9.4 (right) units of them, as it does in the reference. */}
        <rect x="32" y="99" width="13" height="28" rx="6.5" fill="#5f6878" stroke="#828b98" strokeWidth="2" />
        <rect x="155" y="99" width="13" height="28" rx="6.5" fill="#5f6878" stroke="#828b98" strokeWidth="2" />

        <path d="M84 154h32v12q0 7-16 9-16-2-16-9z" fill="#3f4652" stroke="#828b98" strokeWidth="2" />

        {/* 108 x 90, not 108 x 106. The reference's helmet body measures 107.6 x 89.8 -
            an aspect of 1.199 - and ours was 1.019, which is a square rather than the oblong
            the artwork actually draws. The 16 units come off the TOP, which is also what
            seats the hair lower on the head.

            **The top corners are 20 and the bottom ones 30, which is why this is a path and
            not a rect** - `rx` would apply one radius to all four, and flattening the crown
            that way squares off the chin as well. Moving the crown DOWN to flatten it instead
            pulls the head away from the hair and reopens the temples - measured, four holes at
            crown 72, the largest 126 square units. A smaller top radius does the opposite: it
            makes the head bigger there, so it can only ever cover more.

            **And it carries no outline at all, which is why the numbers are quarters.** The
            head used to be stroked in a flat #828b98 on a fill that is a gradient, and a flat
            line on a graded surface cannot read the same on both sides: measured, the fill
            around it was 164-169 in luminance on the left against a 138 line - a dark band
            along the hairline - and 128-135 on the right, where the very same line was
            brighter than its surroundings and vanished. Painting the stroke with the fill's
            own gradient still left a seam, and always would: a stroke's outer half sits
            EARLIER in the gradient than the fill beside it, so it is lighter by a few units
            wherever it goes.

            So the stroke is gone and its width is baked into the shape - every coordinate
            here is the old one grown by 1.25, half of the 2.5 it used to carry. The painted
            silhouette is identical to the unit, the head still fills the outline the hair was
            fitted to, and there is nothing left that can be a different colour from the
            forehead. */}
        <path d="M66 66.75H134A21.25 21.25 0 0 1 155.25 88V128A31.25 31.25 0 0 1 124 159.25H76A31.25 31.25 0 0 1 44.75 128V88A21.25 21.25 0 0 1 66 66.75Z"
          fill={`url(#head-${uid})`} />

        {/* The hair goes on top of the head, in the reference's own two golds: the mass, and
            then the darker strands over it.

            Behind the head it needed something invented to hide a seam every single time. The
            outline's inner boundary is the source helmet's, so wherever our head is the
            smaller of the two, the crescent between them belongs to neither and shows the
            page through - and filling that crescent with hair reads as exactly what it is, a
            gold patch behind the ears. In front, the cut-out simply lies on the head the way
            hair does, and there is no seam to hide.

            The strands were pulled off the silhouette's rim before tracing and so cannot
            overshoot the mass they sit on. No clip needed, and the lit edge stays lit. */}
        <path d={HAIR_MASS} fill={`url(#hair-${uid})`} />

        {/* The shaded locks and the lit ones, each outlined in a line one step further along
            the same falloff. The outlines are what stop the hair reading as areas of colour
            and make it read as drawn.

            They cost no geometry: they are strokes on these two paths, and a stroke sits
            exactly on the boundary of the shape it outlines - so it cannot move a shape by
            any amount at all. That is the whole reason this is safe to add to a silhouette
            that is already right. The clip keeps every line inside the mane. */}
        <g clipPath={`url(#mane-${uid})`}>
          {/* One band per strand thickness, all filled identically - only the outline width
              differs. A stroke takes half its width out of each side of what it outlines, so
              a single width for all of them ate the thin strands alive: 0.9 units on a
              1.26-unit strand is 71% of it, the two sides of its own outline met in the
              middle, and a fine line came out a smear. Five of the thirteen strands are
              under 1.8 units wide.

              The rounded joins are for the same reason at the other end: a mitre on the
              acute point a lock tapers to shoots a spike several times the stroke width. */}
          {HAIR_STRAND_TIERS.map(({ path }) => (
            <path key={path.slice(0, 24)} d={path} fill={`url(#strand-${uid})`} />
          ))}

          {/* The outlines are a layer of their own so the fade can touch them and nothing
              else. Every fill above is drawn at full strength wherever it falls. */}
          <g mask={`url(#edge-fade-${uid})`}>
            {HAIR_STRAND_TIERS.map(({ path, width }) => (
              <path key={path.slice(0, 24)} d={path} fill="none"
                stroke={`url(#edge-dark-${uid})`} strokeWidth={width}
                strokeLinejoin="round" strokeLinecap="round" />
            ))}
          </g>

          {/* The lit locks are the ones bordering the shaded ones, so this lifts a rim of
              light around every shadow without a single dilation - and therefore without
              rounding any of the points the locks taper to. The two are disjoint by
              construction.

              It carries no outline of its own, and that is not an omission: being adjacent to
              the shaded locks, it SHARES their boundary. Outlining both put a dark line and a
              light line on the same edge, half a stroke each, and two contrasting sub-pixel
              lines side by side read as aliasing rather than as line work. One line per
              boundary. */}
          <path d={HAIR_HIGHLIGHTS} fill={`url(#glow-${uid})`} />
        </g>

        {/* The visor sits at 92, six units lower than it was drawn originally.
 
            The forehead's height is not set by the head at all - the head's own top edge is
            under the hair from end to end. It is the gap between where the hair stops (y 79 on
            the centre line) and where the visor starts, so the visor is the only thing that
            can change it. Six units takes the forehead from 12 to 18.
 
            Everything that lives in the visor moved with it by the same six: the glass, the
            clip that holds the chart inside it, all five chart states, their end dots, and the
            two mouth lines. */}
        <rect x="58" y="92" width="84" height="40" rx="18" fill="#0b0e13" stroke="#828b98" strokeWidth="2" />

        <g clipPath={`url(#visor-${uid})`} className="larson-visor">
          <polyline points={visor.points} fill="none" stroke={visor.stroke}
            strokeWidth="3.6" strokeLinecap="round" strokeLinejoin="round" />

          {visor.dot && <circle cx={visor.dot.cx} cy={visor.dot.cy} r={visor.dot.r} fill={visor.dot.fill} />}
        </g>

        <g stroke="#828b98" strokeWidth="2.6" strokeLinecap="round">
          <path d="M86 145h28" />
          <path d="M92 152h16" />
        </g>
      </g>

      {variant === 'devil' && HORNS.map((horn) => (
        <path key={horn} d={horn} fill={`url(#horn-${uid})`} />
      ))}

    </svg>
  )
}

export default LarsonMark
