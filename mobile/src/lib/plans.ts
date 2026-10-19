import { useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';

import { supabase } from './supabase';
import type { ReviewAllowance } from './types';

/** Prices agreed 19 Oct 2026. Purchases go through the App Store once the first build is up. */
export const PLANS = {
  free: { price: '£0', per: 'forever', points: ['New-sets feed and alerts', 'Projects, sends and your grade pyramid', '3 climb reviews every month', 'Share any review with the tracking on'] },
  grip: {
    monthly: '£4.99',
    yearly: '£34.99',
    points: ['Up to 20 reviews a month', 'Three notes per climb', 'Next-go notes on your widget', 'New sports as they land'],
  },
  founding: { price: '£24.99', per: 'a year, locked for life', limit: 'First 500 climbers' },
} as const;

export function useAllowance() {
  const [allowance, setAllowance] = useState<ReviewAllowance | null>(null);
  const load = useCallback(async () => {
    const { data } = await supabase.rpc('review_allowance');
    const row = Array.isArray(data) ? data[0] : data;
    setAllowance((row as ReviewAllowance) ?? null);
  }, []);
  useFocusEffect(
    useCallback(() => {
      load();
    }, [load]),
  );
  return { allowance, load };
}

export async function myReferralCode(): Promise<string> {
  const { data, error } = await supabase.rpc('my_referral_code');
  if (error) throw error;
  return data as string;
}

/** Both of you get a free month. Throws with a readable message when the code can't be used. */
export async function redeemReferral(code: string) {
  const { error } = await supabase.rpc('redeem_referral', { p_code: code.trim() });
  if (error) throw new Error(error.message);
}
