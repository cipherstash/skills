package metrics_test

import (
	"sync"
	"testing"

	"example.com/golang-practices/metrics"
)

func TestCounterIsSafeForConcurrentUse(t *testing.T) {
	var c metrics.Counter
	var wg sync.WaitGroup
	for i := 0; i < 50; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			c.Inc()
		}()
	}
	wg.Wait()
	if got := c.Value(); got != 50 {
		t.Fatalf("Value() = %d, want 50", got)
	}
}
