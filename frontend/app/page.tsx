import Link from 'next/link';
import { ArrowRight, BarChart3, Bot, Plug } from 'lucide-react';
import type { Metadata } from 'next';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { HealthStatus } from '@/components/health-status';

export const metadata: Metadata = {
  title: 'Dashboard',
  description: 'Quantitative Stock-Selection — PRISMA Dashboard',
};

const features = [
  {
    icon: BarChart3,
    title: 'Ranking-Engine',
    description:
      'Funf quantitative Modelle (Quality Classic, Alpha, Trend Momentum, Value Alpha Potential, Diversification) berechnen je Aktie einen Rang. Aggregiert zum Total Rank mit konfigurierbaren Gewichten.',
  },
  {
    icon: Bot,
    title: 'AI-Research-Memos',
    description:
      'Claude-generierte Research-Memos fur die Top-N-Titel. Strukturierter Output per Pydantic-Schema: Starken, Risiken, Widerspruchserkennung und ein pragananter One-Liner.',
  },
  {
    icon: Plug,
    title: 'MCP-Integration',
    description:
      'PRISMA als MCP-Server direkt aus Claude Desktop nutzbar. Naturlichsprachliche Abfragen wie "Zeig mir SPI-Titel, die in Quality und Trend Top-20% sind."',
  },
] as const;

export default function HomePage() {
  return (
    <div className="space-y-12">
      {/* Hero */}
      <section className="space-y-4 py-8">
        <div className="space-y-2">
          <h1 className="text-4xl font-black tracking-tight sm:text-5xl">PRISMA</h1>
          <p className="max-w-2xl text-lg text-muted-foreground">
            Quantitative Stock-Selection zerlegt in analytische Dimensionen
          </p>
        </div>
        <p className="max-w-2xl text-muted-foreground">
          Wie ein optisches Prisma weisses Licht in seine Spektralfarben zerlegt, analysiert PRISMA
          Unternehmen entlang der Dimensionen Quality, Trend, Value und Risk — nachvollziehbar,
          reproduzierbar und ohne Financial Advice.
        </p>
      </section>

      {/* API Health */}
      <section className="max-w-md">
        <HealthStatus />
      </section>

      {/* Features */}
      <section className="space-y-4">
        <h2 className="text-xl font-semibold">Kernfunktionen</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          {features.map((feature) => {
            const Icon = feature.icon;
            return (
              <Card key={feature.title}>
                <CardHeader className="pb-3">
                  <div className="mb-2 flex h-9 w-9 items-center justify-center rounded-md bg-primary/10">
                    <Icon className="h-5 w-5 text-primary" />
                  </div>
                  <CardTitle className="text-base">{feature.title}</CardTitle>
                </CardHeader>
                <CardContent>
                  <CardDescription>{feature.description}</CardDescription>
                </CardContent>
              </Card>
            );
          })}
        </div>
      </section>

      {/* CTA */}
      <section>
        <Button asChild size="lg">
          <Link href="/universes">
            Los geht&apos;s
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </section>
    </div>
  );
}
