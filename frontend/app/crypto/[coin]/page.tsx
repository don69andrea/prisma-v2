import type { Metadata } from 'next';
import { CoinDetailClient } from './coin-detail-client';

const COINS = ['btc','eth','sol','bnb','xrp','ada','avax','doge','link','dot'];

export async function generateStaticParams() {
  return COINS.map(coin => ({ coin }));
}

export async function generateMetadata({ params }: { params: { coin: string } }): Promise<Metadata> {
  return { title: `${params.coin.toUpperCase()} — PRISMA Krypto-Signale` };
}

export default function CoinPage({ params }: { params: { coin: string } }) {
  return <CoinDetailClient coin={params.coin.toUpperCase()} />;
}
