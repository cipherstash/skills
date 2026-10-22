# Concurrency & Stress Tests

## Contents

- [Multi-threaded runtime](#multi-threaded-runtime)
- [CountingState pattern](#countingstate-pattern)
- [Real Axum server for latency simulation](#real-axum-server-for-latency-simulation)
- [Stress test structure](#stress-test-structure)

Use a separate `stress_tests` module for tests that verify concurrency properties. Examples target `axum` 0.8 and `tokio` 1.x. Assertion messages and the other conventions in the main skill still apply.

## Multi-threaded runtime

```rust
#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn test_stress_initial_auth() {
    // Real thread concurrency for meaningful contention testing
}
```

## CountingState pattern

Track in-flight, peak, and total request counts with atomics:

```rust
#[derive(Clone)]
struct CountingState {
    total: Arc<AtomicUsize>,
    current: Arc<AtomicUsize>,
    peak: Arc<AtomicUsize>,
}

impl CountingState {
    fn new() -> Self {
        Self {
            total: Arc::new(AtomicUsize::new(0)),
            current: Arc::new(AtomicUsize::new(0)),
            peak: Arc::new(AtomicUsize::new(0)),
        }
    }

    fn enter(&self) {
        self.total.fetch_add(1, Ordering::SeqCst);
        let prev = self.current.fetch_add(1, Ordering::SeqCst);
        self.peak.fetch_max(prev + 1, Ordering::SeqCst);
    }

    fn exit(&self) {
        self.current.fetch_sub(1, Ordering::SeqCst);
    }
}
```

The stress test below reads the counters through `total()` and `peak()` accessors; add them as plain `load(Ordering::SeqCst)` getters.

## Real Axum server for latency simulation

Use a real Axum server (not mocktail) when you need to simulate latency for concurrency assertions:

```rust
#[derive(Clone)]
struct DelayedAuthState {
    counting: CountingState,
    delay: Duration,
}

async fn delayed_auth_handler(
    axum::extract::State(state): axum::extract::State<DelayedAuthState>,
) -> axum::Json<serde_json::Value> {
    state.counting.enter();
    tokio::time::sleep(state.delay).await;
    state.counting.exit();
    axum::Json(serde_json::json!({ "accessToken": "refreshed", "expiry": 3600 }))
}

async fn start_axum_server(state: DelayedAuthState) -> (Url, CountingState) {
    let counting = state.counting.clone();
    let app = axum::Router::new()
        .route("/api/authorise", axum::routing::post(delayed_auth_handler))
        .with_state(state);
    let listener = tokio::net::TcpListener::bind("127.0.0.1:0").await.unwrap();
    let addr = listener.local_addr().unwrap();
    tokio::spawn(async move { axum::serve(listener, app).await.unwrap() });
    (Url::parse(&format!("http://{addr}")).unwrap(), counting)
}
```

## Stress test structure

```rust
const CONCURRENCY: usize = 50;

#[tokio::test(flavor = "multi_thread", worker_threads = 4)]
async fn test_stress_initial_auth() {
    let state = DelayedAuthState { counting: CountingState::new(), delay: Duration::from_millis(200) };
    let (base_url, stats) = start_axum_server(state).await;
    let strategy = Arc::new(make_strategy(base_url));

    let mut handles = Vec::with_capacity(CONCURRENCY);
    for _ in 0..CONCURRENCY {
        let s = Arc::clone(&strategy);
        handles.push(tokio::spawn(async move { s.get_token().await.unwrap() }));
    }

    let results: Vec<_> = {
        let mut results = Vec::with_capacity(handles.len());
        for handle in handles {
            results.push(handle.await.unwrap());
        }
        results
    };

    for token in &results {
        assert_eq!(token.as_str(), "refreshed", "all callers should receive the same token");
    }

    assert_eq!(stats.total(), 1, "only one auth request should be made");
    assert_eq!(stats.peak(), 1, "at most one in-flight request at a time");
}
```
