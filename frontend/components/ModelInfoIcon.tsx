import { InfoPopover } from './InfoPopover';
import { MODEL_INFO, type ModelKey } from '@/lib/model-info';

interface Props {
  modelKey: ModelKey;
}

export function ModelInfoIcon({ modelKey }: Props) {
  const info = MODEL_INFO[modelKey];
  return (
    <InfoPopover ariaLabel={`Info zu ${info.label}`}>
      <p>{info.description}</p>
    </InfoPopover>
  );
}
