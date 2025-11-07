export const DE39_MAP = {
  '00': { status: 'approved', message: 'Accepted' },
  '05': { status: 'declined', message: 'Declined — check details' },
  '14': { status: 'invalid', message: 'Invalid account or card number' },
  '51': { status: 'insufficient_funds', message: 'Insufficient funds' },
  '91': { status: 'issuer_unavailable', message: 'Issuer not available — try later', retryable: true },
  '96': { status: 'system_error', message: 'Temporary system error — please retry', retryable: true }
};

export function interpretProcessorResponse(body) {
  // body is parsed JSON from backend
  const code = (body && (body.code || (body.response && body.response.fields && body.response.fields['39']))) || null;
  const txn = body && body.response && body.response.txn_id;
  const mapping = DE39_MAP[String(code)] || { status: 'unknown_error', message: body && body.error || 'Processing error' };
  return {
    status: mapping.status,
    code: code,
    message: body && body.response && body.response.message ? body.response.message : mapping.message,
    retryable: !!mapping.retryable,
    txn_id: txn
  };
}
