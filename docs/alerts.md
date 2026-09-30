# Alert rules and runbooks

All three alerts notify `#k4-l3b-alerts`. Start with the dashboard symptom, use
`correlation_id` to find affected requests in `data/logs.jsonl`, then inspect the
matching trace in Langfuse before choosing a mitigation.

## Alert 1

- **Name:** `HighLatencyP95`
- **Severity / duration:** warning for 5 minutes
- **Condition:** `p95(response_sent.latency_ms) > 3000 ms`
- **User impact:** responses take longer than the 3-second latency SLO.
- **Checks:**
  1. Confirm the latency panel's P95/P99 and the time range where they rose.
  2. Find `response_sent` log records in that range with high `latency_ms`; note their `correlation_id` values.
  3. Open the matching Langfuse traces and compare retrieval and generation durations.
- **Mitigation:** if generation regressed after a prompt change, return the `production` label to the last known-good prompt version. If retrieval is slow, disable the practice `rag_slow` incident or restore the retrieval service/configuration.
- **Owner:** `student-2A202602503`

## Alert 2

- **Name:** `HighRequestErrorRate`
- **Severity / duration:** critical for 5 minutes
- **Condition:** `request_failed / request_received > 2%`
- **User impact:** more than the error-rate guardrail of requests fail.
- **Checks:**
  1. Confirm the errors panel and compare failed requests with total request traffic.
  2. Inspect `request_failed` records for `error_type`, `tool_name`, `tool_success`, and `correlation_id`.
  3. Open matching traces and identify the failed observation and its status message.
- **Mitigation:** disable the matching practice incident if one is active. Otherwise restore the failing dependency or last known-good prompt/configuration, then check whether new requests succeed.
- **Owner:** `student-2A202602503`

## Alert 3

- **Name:** `LowRetrievalSuccess`
- **Severity / duration:** warning for 5 minutes
- **Condition:** retrieval `tool_success` rate is below 90% across retrieval attempts.
- **User impact:** answers may lack relevant context and become less reliable.
- **Checks:**
  1. Confirm the errors panel's retrieval success rate and the affected time range.
  2. Filter `request_failed` logs for `tool_name=retrieval` and `tool_success=false`; collect their `correlation_id` values.
  3. Open matching Langfuse traces and inspect the `retrieve-context` observation and its error or duration.
- **Mitigation:** disable the practice `tool_fail` incident if active. Otherwise restore the retrieval/vector-store dependency and confirm successful retrievals before closing the alert.
- **Owner:** `student-2A202602503`
