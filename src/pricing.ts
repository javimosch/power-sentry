// French electricity pricing (EDF Tarif Bleu)
// Heures pleines (peak hours): 22h-6h (10pm-6am)
// Heures creuses (off-peak hours): 6h-22h (6am-10pm)
// Prices as of 2024 (approximate)

export const FRENCH_PRICING = {
  peakPrice: 0.2795, // € per kWh during peak hours
  offPeakPrice: 0.2068, // € per kWh during off-peak hours
  peakHours: { start: 22, end: 6 } // 22h to 6h next day
};

export function getCurrentPrice(timestamp?: number): number {
  const date = timestamp ? new Date(timestamp) : new Date();
  const hour = date.getHours();
  
  // Peak hours: 22h-6h (wraps around midnight)
  const isPeak = hour >= 22 || hour < 6;
  
  return isPeak ? FRENCH_PRICING.peakPrice : FRENCH_PRICING.offPeakPrice;
}

export function getPricePeriod(timestamp?: number): 'peak' | 'off-peak' {
  const date = timestamp ? new Date(timestamp) : new Date();
  const hour = date.getHours();
  
  return (hour >= 22 || hour < 6) ? 'peak' : 'off-peak';
}

export function formatPrice(cents: number): string {
  return `€${cents.toFixed(4)}`;
}
