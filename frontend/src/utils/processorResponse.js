import { interpretProcessorResponse } from './utils/processorResponse';

async function submitPayout(payload) {
  const res = await fetch('/payout', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const body = await res.json();
  const result = interpretProcessorResponse(body);
  console.log('UI normalized result:', result);
}
