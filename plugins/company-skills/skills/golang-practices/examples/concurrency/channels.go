package concurrency

import (
	"context"
	"sync"
)

// Generate sends 0 to n-1 on the returned channel, then closes it. It stops
// early and closes the channel when ctx ends.
func Generate(ctx context.Context, n int) <-chan int {
	out := make(chan int)
	go func() {
		defer close(out)
		for i := range n {
			select {
			case out <- i:
			case <-ctx.Done():
				return
			}
		}
	}()
	return out
}

// Double sends twice each value from in. It closes its output when in is
// closed or ctx ends, so it stops even if in is never closed.
func Double(ctx context.Context, in <-chan int) <-chan int {
	out := make(chan int)
	go func() {
		defer close(out)
		for {
			select {
			case v, ok := <-in:
				if !ok {
					return
				}
				select {
				case out <- v * 2:
				case <-ctx.Done():
					return
				}
			case <-ctx.Done():
				return
			}
		}
	}()
	return out
}

// FanOut starts n Double stages that share in.
func FanOut(ctx context.Context, in <-chan int, n int) []<-chan int {
	outs := make([]<-chan int, n)
	for i := range outs {
		outs[i] = Double(ctx, in)
	}
	return outs
}

// Merge sends every value from every input on one channel. It closes its
// output when all inputs are closed or ctx ends.
func Merge(ctx context.Context, ins ...<-chan int) <-chan int {
	out := make(chan int)
	var wg sync.WaitGroup
	for _, in := range ins {
		wg.Add(1)
		go func() { // Go 1.22+: each iteration has its own in
			defer wg.Done()
			for {
				select {
				case v, ok := <-in:
					if !ok {
						return
					}
					select {
					case out <- v:
					case <-ctx.Done():
						return
					}
				case <-ctx.Done():
					return
				}
			}
		}()
	}
	go func() {
		wg.Wait()
		close(out)
	}()
	return out
}

// Pipeline squares each value from in and passes on the even results. Both
// stages stop when in is closed or ctx ends.
func Pipeline(ctx context.Context, in <-chan int) <-chan int {
	squares := stage(ctx, in, func(n int) (int, bool) { return n * n, true })
	return stage(ctx, squares, func(n int) (int, bool) { return n, n%2 == 0 })
}

// stage runs one pipeline step in its own goroutine. f returns the value to
// send and whether to send it.
func stage(ctx context.Context, in <-chan int, f func(int) (int, bool)) <-chan int {
	out := make(chan int)
	go func() {
		defer close(out)
		for {
			select {
			case n, ok := <-in:
				if !ok {
					return
				}
				v, keep := f(n)
				if !keep {
					continue
				}
				select {
				case out <- v:
				case <-ctx.Done():
					return
				}
			case <-ctx.Done():
				return
			}
		}
	}()
	return out
}
