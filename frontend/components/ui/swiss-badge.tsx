import { Badge } from '@/components/ui/badge';

interface Props {
  exchange: string | null;
  className?: string;
}

export function SwissBadge({ exchange, className }: Props) {
  if (exchange !== 'XSWX') return null;
  return (
    <Badge variant="outline" className={`font-mono text-xs text-sky-700 border-sky-300 ${className ?? ''}`}>
      🇨🇭 XSWX
    </Badge>
  );
}
