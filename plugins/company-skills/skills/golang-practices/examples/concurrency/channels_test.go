package concurrency_test

import (
	"context"
	"slices"
	"testing"
	"time"

	"example.com/golang-practices/concurrency"
)

func collect(t *testing.T, ch <-chan int) []int {
	t.Helper()
	var got []int
	timeout := time.After(prompt)
	for {
		select {
		case v, ok := <-ch:
			if !ok {
				return got
			}
			got = append(got, v)
		case <-timeout:
			t.Fatal("channel was not closed")
			return nil
		}
	}
}

func TestGenerate(t *testing.T) {
	got := collect(t, concurrency.Generate(context.Background(), 4))
	if want := []int{0, 1, 2, 3}; !slices.Equal(got, want) {
		t.Fatalf("Generate = %v, want %v", got, want)
	}
}

func TestPipelineSquaresAndKeepsEvenNumbers(t *testing.T) {
	ctx := context.Background()
	got := collect(t, concurrency.Pipeline(ctx, concurrency.Generate(ctx, 6)))
	if want := []int{0, 4, 16}; !slices.Equal(got, want) {
		t.Fatalf("Pipeline = %v, want %v", got, want)
	}
}

func TestFanOutFanInDoublesEveryValue(t *testing.T) {
	ctx := context.Background()
	got := collect(t, concurrency.Merge(ctx, concurrency.FanOut(ctx, concurrency.Generate(ctx, 10), 3)...))
	slices.Sort(got)
	if want := []int{0, 2, 4, 6, 8, 10, 12, 14, 16, 18}; !slices.Equal(got, want) {
		t.Fatalf("fan-out, fan-in = %v, want %v", got, want)
	}
}

// An input channel that is never closed is the case the upstream stages leaked
// on: they ranged over it and only checked ctx when sending. Each stage must
// also stop waiting to receive once ctx is cancelled.
func TestStagesStopOnCancelWhenTheInputStaysOpen(t *testing.T) {
	stages := map[string]func(context.Context, <-chan int) <-chan int{
		"Pipeline": concurrency.Pipeline,
		"Double":   concurrency.Double,
		"Merge": func(ctx context.Context, in <-chan int) <-chan int {
			return concurrency.Merge(ctx, in)
		},
	}
	for name, stage := range stages {
		t.Run(name, func(t *testing.T) {
			ctx, cancel := context.WithCancel(context.Background())
			out := stage(ctx, make(chan int)) // never closed, never sent on
			cancel()
			collect(t, out) // fails if the stage's goroutine never closes out
		})
	}
}

func TestGenerateStopsOnCancelWhenNobodyReads(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	out := concurrency.Generate(ctx, 1_000_000)
	<-out
	cancel()
	collect(t, out)
}
