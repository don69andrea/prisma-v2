import { FileText } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

export function MemoPanel() {
  return (
    <Card className="border-dashed bg-muted/30">
      <CardHeader className="pb-2">
        <CardTitle className="text-base font-medium flex items-center gap-2">
          <FileText className="h-4 w-4 text-muted-foreground" />
          Research Memo
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col items-center justify-center py-8 gap-2 text-center text-muted-foreground">
          <FileText className="h-8 w-8 opacity-30" />
          <p className="text-sm">
            KI-Memo noch nicht verfügbar — Layer-1-Integration folgt.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
