import React, {useMemo} from 'react';
import {Easing, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';

/** One continuous authored SVG route, expressed as cubic Bézier segments. */
const segments: readonly [number, number][][] = [
  [[160, 830], [300, 845], [320, 480], [525, 492]],
  [[525, 492], [710, 505], [680, 760], [886, 735]],
  [[886, 735], [1080, 710], [961, 340], [1215, 325]],
  [[1215, 325], [1470, 310], [1340, 620], [1570, 570]],
  [[1570, 570], [1712, 540], [1675, 372], [1760, 268]],
];

const route = 'M 160 830 ' + segments.map((s) => `C ${s[1].join(' ')} ${s[2].join(' ')} ${s[3].join(' ')}`).join(' ');

const cubic = (s: readonly [number, number][], t: number): [number, number] => {
  const k = 1 - t;
  return [0, 1].map((axis) =>
    k * k * k * s[0][axis] + 3 * k * k * t * s[1][axis] +
    3 * k * t * t * s[2][axis] + t * t * t * s[3][axis]
  ) as [number, number];
};

// Arc-length table is computed once, outside React. The same frame always
// resolves to the same point, including out-of-order and parallel renders.
const samples: {distance: number; x: number; y: number}[] = [];
let total = 0;
let previous: [number, number] | null = null;
for (const segment of segments) {
  for (let i = previous === null ? 0 : 1; i <= 160; i++) {
    const [x, y] = cubic(segment, i / 160);
    if (previous) total += Math.hypot(x - previous[0], y - previous[1]);
    samples.push({distance: total, x, y});
    previous = [x, y];
  }
}
const pathLength = total;
const pointAt = (ratio: number): [number, number] => {
  const target = Math.max(0, Math.min(1, ratio)) * pathLength;
  let lo = 0;
  let hi = samples.length - 1;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (samples[mid].distance < target) lo = mid + 1;
    else hi = mid;
  }
  const right = samples[lo];
  const left = samples[Math.max(0, lo - 1)];
  const span = right.distance - left.distance;
  const fraction = span ? (target - left.distance) / span : 0;
  return [left.x + fraction * (right.x - left.x), left.y + fraction * (right.y - left.y)];
};

export const DotToPath: React.FC = () => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const progress = interpolate(frame, [0.33 * fps, 5.1 * fps], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.bezier(0.45, 0.05, 0.27, 1),
  });
  // Text is a half-step behind the dot. It cannot appear until the dot has
  // passed the corresponding position on the line, even at a random seek.
  const textProgress = Math.max(0, progress - 0.012);
  const [x, y] = useMemo(() => pointAt(progress), [progress]);
  const arrival = interpolate(frame, [4.95 * fps, 5.65 * fps], [0, 1], {
    extrapolateLeft: 'clamp', extrapolateRight: 'clamp',
    easing: Easing.bezier(0.16, 1, 0.3, 1),
  });

  return <svg width={1920} height={1080} viewBox="0 0 1920 1080" role="img" aria-label="A single dot draws a route and reveals curved text only after passing it">
    <defs>
      <linearGradient id="ink" x1={160} y1={0} x2={1760} y2={0} gradientUnits="userSpaceOnUse">
        <stop offset="0" stopColor="#43C5D0"/>
        <stop offset=".5" stopColor="#B8EFE7"/>
        <stop offset="1" stopColor="#F4CA96"/>
      </linearGradient>
      <radialGradient id="glow"><stop stopColor="#AAFFF0" stopOpacity={0.32}/><stop offset="1" stopColor="#AAFFF0" stopOpacity={0}/></radialGradient>
      <mask id="text-behind-dot" maskUnits="userSpaceOnUse" x={0} y={0} width={1920} height={1080}>
        <path d={route} fill="none" stroke="white" strokeWidth={150}
          strokeDasharray={`${pathLength} ${pathLength}`}
          strokeDashoffset={pathLength * (1 - textProgress)} strokeLinecap="butt"/>
      </mask>
    </defs>
    <rect width={1920} height={1080} fill="#09141D"/>
    <path d={route} fill="none" stroke="url(#ink)" strokeWidth={8} strokeLinecap="round"
      strokeDasharray={`${pathLength} ${pathLength}`}
      strokeDashoffset={pathLength * (1 - progress)}/>
    <g mask="url(#text-behind-dot)" fill="#E9F7EE" fontFamily="Arial, sans-serif" fontSize={38} fontWeight={700} letterSpacing={4}>
      <text dy={-23}><textPath href="#route-reference" startOffset="6%">A SINGLE DOT</textPath></text>
      <text dy={-23}><textPath href="#route-reference" startOffset="39%">FINDS ITS WAY</textPath></text>
      <text dy={-23}><textPath href="#route-reference" startOffset="70%">BECOMES A PATH</textPath></text>
    </g>
    <circle cx={x} cy={y} r={91} fill="url(#glow)"/>
    <circle cx={x} cy={y} r={24 + arrival * 10} fill="#A6F2E7" opacity={0.22}/>
    <circle cx={x} cy={y} r={11 + arrival * 3} fill={arrival > 0.5 ? '#F4CA96' : '#F8FCF2'}/>
    <circle cx={1760} cy={268} r={22 + 24 * arrival} fill="none" stroke="#F4CA96" strokeWidth={2.5} opacity={arrival * 0.8}/>
    {/* The reference defines the geometric baseline but never paints ahead of the dot. */}
    <path id="route-reference" d={route} fill="none" stroke="none"/>
  </svg>;
};
