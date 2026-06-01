'use client';

import { useRouter } from 'next/navigation';
import { useMutation } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { createRun } from '@/lib/api/runs';

interface Props {
  universe: { id: string; name: string } | null;
  onClose: () => void;
}

export function StartRankingDialog({ universe, onClose }: Props) {
  const router = useRouter();

  const mutation = useMutation({
    mutationFn: () => {
      if (!universe) throw new Error('Kein Universe ausgewählt');
      return createRun(universe.id);
    },
    onSuccess: (run) => router.push(`/rankings/${run.id}`),
  });

  return (
    <Dialog
      open={universe !== null}
      onOpenChange={(open) => {
        if (!open && !mutation.isPending) {
          mutation.reset();
          onClose();
        }
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Ranking starten?</DialogTitle>
          <DialogDescription>
            Möchtest du direkt einen Ranking-Run für{' '}
            <strong>{universe?.name}</strong> starten?
          </DialogDescription>
        </DialogHeader>

        {mutation.isError && (
          <p className="text-sm text-destructive" role="alert">
            {mutation.error instanceof Error
              ? mutation.error.message
              : 'Fehler beim Starten des Rankings'}
          </p>
        )}

        <DialogFooter className="gap-2 sm:gap-0">
          <Button
            variant="outline"
            onClick={onClose}
            disabled={mutation.isPending}
          >
            Nein
          </Button>
          <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
            {mutation.isPending && (
              <Loader2 className="h-4 w-4 animate-spin mr-2" />
            )}
            Ja, Ranking starten
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
