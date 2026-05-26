import { describe, it, expect } from 'vitest';

import {
  MODEL_INFO,
  MODEL_KEYS,
  SWEET_SPOT_DEFINITION,
  getSweetSpotModels,
  type ModelKey,
} from '../model-info';

describe('MODEL_INFO', () => {
  it('hat einen Eintrag für jeden der 5 Modell-Keys', () => {
    expect(MODEL_KEYS).toEqual([
      'quality_classic',
      'alpha',
      'trend_momentum',
      'value_alpha_potential',
      'diversification',
    ]);
    for (const key of MODEL_KEYS) {
      expect(MODEL_INFO[key].label).toBeTruthy();
      expect(MODEL_INFO[key].description.length).toBeGreaterThan(20);
    }
  });

  it('SWEET_SPOT_DEFINITION erwähnt 25% und 3 von 5', () => {
    expect(SWEET_SPOT_DEFINITION).toMatch(/25 ?%/);
    expect(SWEET_SPOT_DEFINITION).toMatch(/3 von 5|3\/5/);
  });
});

describe('getSweetSpotModels', () => {
  const allFive: Record<ModelKey, number | null> = {
    quality_classic: 1,
    alpha: 2,
    trend_momentum: 3,
    value_alpha_potential: 4,
    diversification: 5,
  };

  it('totalStocks=20, alle ranks <= 5 → alle 5 Modelle', () => {
    const result = getSweetSpotModels(allFive, 20);
    expect(result).toHaveLength(5);
  });

  it('totalStocks=20, Schwelle ist ceil(20*0.25)=5 → rank=5 zählt noch', () => {
    const ranks: Record<ModelKey, number | null> = {
      quality_classic: 5,
      alpha: 6,
      trend_momentum: null,
      value_alpha_potential: 100,
      diversification: 1,
    };
    const result = getSweetSpotModels(ranks, 20);
    expect(result).toEqual(['quality_classic', 'diversification']);
  });

  it('totalStocks=4, Schwelle ist ceil(4*0.25)=1 → nur rank=1 zählt', () => {
    const ranks: Record<ModelKey, number | null> = {
      quality_classic: 1,
      alpha: 2,
      trend_momentum: 1,
      value_alpha_potential: 3,
      diversification: 4,
    };
    const result = getSweetSpotModels(ranks, 4);
    expect(result).toEqual(['quality_classic', 'trend_momentum']);
  });

  it('alle ranks > Schwelle → leeres Array', () => {
    const ranks: Record<ModelKey, number | null> = {
      quality_classic: 10,
      alpha: 11,
      trend_momentum: 12,
      value_alpha_potential: 13,
      diversification: 14,
    };
    const result = getSweetSpotModels(ranks, 20);
    expect(result).toEqual([]);
  });

  it('null-Ranks werden ignoriert (nicht als Top-25% gezählt)', () => {
    const ranks: Record<ModelKey, number | null> = {
      quality_classic: null,
      alpha: null,
      trend_momentum: null,
      value_alpha_potential: 1,
      diversification: 2,
    };
    const result = getSweetSpotModels(ranks, 20);
    expect(result).toEqual(['value_alpha_potential', 'diversification']);
  });

  it('Reihenfolge folgt MODEL_KEYS-Reihenfolge', () => {
    const ranks: Record<ModelKey, number | null> = {
      diversification: 1,
      quality_classic: 1,
      alpha: 1,
      trend_momentum: 1,
      value_alpha_potential: 1,
    };
    const result = getSweetSpotModels(ranks, 20);
    expect(result).toEqual([
      'quality_classic',
      'alpha',
      'trend_momentum',
      'value_alpha_potential',
      'diversification',
    ]);
  });
});
