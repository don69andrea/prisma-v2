'use client';

import { useEffect, useState } from 'react';
import { Moon, Sun } from 'lucide-react';

export function ThemeToggle() {
  const [dark, setDark] = useState(true);

  useEffect(() => {
    const stored = localStorage.getItem('prisma-theme');
    const isDark = stored ? stored === 'dark' : true;
    setDark(isDark);
    document.documentElement.classList.toggle('dark', isDark);
  }, []);

  const toggle = () => {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle('dark', next);
    localStorage.setItem('prisma-theme', next ? 'dark' : 'light');
  };

  return (
    <button
      onClick={toggle}
      title={dark ? 'Light Mode' : 'Dark Mode'}
      className="inline-flex h-6 w-6 items-center justify-center rounded-full border border-border bg-background/60 text-muted-foreground backdrop-blur transition-colors hover:bg-muted hover:text-foreground"
    >
      {dark ? <Sun className="h-3 w-3" /> : <Moon className="h-3 w-3" />}
    </button>
  );
}
