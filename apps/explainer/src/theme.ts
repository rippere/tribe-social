import { loadFont } from '@remotion/google-fonts/Geist'
import { loadFont as loadMono } from '@remotion/google-fonts/GeistMono'

// Tokens mirror apps/web/app/globals.css (dark x.ai/bot system). The canvas is
// #0F0F0F rather than the site's #0B0B0B so the Higgsfield mascot clips, whose
// studio background renders at #0F0F0F, sit on it without a visible box.
export const C = {
  bg: '#0F0F0F',
  elevated: '#121212',
  panel: '#161615',
  ink: '#F2F2F0',
  ink2: '#1C1C1B',
  muted: '#8E929A',
  line: 'rgba(255, 255, 255, 0.1)',
  fill: 'rgba(255, 255, 255, 0.05)',
  accent: '#5CE1F0',
  accentBg: 'rgba(74, 216, 236, 0.12)',
  amber: '#F5B454',
}

export const FONT = loadFont('normal', { weights: ['400', '500'], subsets: ['latin'] }).fontFamily
export const MONO = loadMono('normal', { weights: ['400'], subsets: ['latin'] }).fontFamily

export const FPS = 30
