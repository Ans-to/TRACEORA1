import {Composition} from 'remotion';
import {DotToPath} from './DotToPath';

export const RemotionRoot = () => (
  <Composition
    id="DotToPath"
    component={DotToPath}
    durationInFrames={210}
    fps={30}
    width={1920}
    height={1080}
  />
);
