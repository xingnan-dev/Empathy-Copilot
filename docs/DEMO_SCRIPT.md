# Golden Demo — C Serum / D Cream

1. Open `case_c_serum_001` for `consumer_001` with no preloaded order Evidence. The consumer
   says: “我刚买的 C 精华用了以后感觉有点不舒服。” The agent calls
   `get_order_history`; Order `A1024` becomes sourced first-purchase Evidence. This proves
   purchase only; all four P0 gaps remain open and no regimen change is created.
2. The consumer says: “9 月 12 日开始用的。” Message `M102` explicitly identifies C Serum
   and `first_use_at=2026-09-12`. Actual first use resolves and C Serum becomes an
   evidence-backed `NEW` regimen change. Feedback onset, recent changes, and severity remain
   open.
3. The consumer says: “最近还换了 D 面霜。” Message `M104` creates D Cream `NEW` with no
   effective date and resolves the recent-change gap. It establishes another recent factor,
   but not concurrency with C Serum.
4. If the consumer additionally confirms “D 面霜也是 9 月 12 日开始用的,” Message `M105`
   records D Cream with `effective_at=2026-09-12`. Only then do C Serum and D Cream share an
   effective date.
5. Separately sourced consumer answers establish feedback onset and reported severity. Once
   all P0 gaps are resolved, the two dated changes yield `ATTRIBUTION_AMBIGUOUS`. Without the
   D date—or with C alone—the result remains `INSUFFICIENT_EVIDENCE`.
6. The agent never says either product caused the reaction. Temporal association is not
   causality, and Phase 1.1 has no automatic `SUPPORTED` path.
7. On a repeat contact, restore the checkpoint and build the Context Passport. The answered
   first-use question and completed order/service/memory tools remain recorded, their facts
   retain Evidence ids, and the agent does not ask the first-use question or execute the same
   completed lookups again.
