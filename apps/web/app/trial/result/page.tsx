import TrialResult from '@/components/trial/TrialResult'

// /trial/result#<result token> — static page; the token stays in the fragment and is
// sent to /api/trial/result as a bearer header, never in a URL.
export default function TrialResultPage() {
  return <TrialResult />
}
