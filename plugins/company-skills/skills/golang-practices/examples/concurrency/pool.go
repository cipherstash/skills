package concurrency

import (
	"context"
	"errors"
	"fmt"
	"sync"
)

// ErrPoolClosed is returned by Submit after Shutdown has been called.
var ErrPoolClosed = errors.New("pool closed")

// Pool runs submitted tasks on a fixed number of goroutines.
type Pool struct {
	tasks    chan func(context.Context)
	quit     chan struct{} // closed by Shutdown: no new tasks
	done     chan struct{} // closed when every worker has exited
	stopOnce sync.Once
	cancel   context.CancelFunc // cancels the context running tasks receive
}

// NewPool starts a pool of n workers. Call Shutdown to stop them.
func NewPool(n int) *Pool {
	ctx, cancel := context.WithCancel(context.Background())
	p := &Pool{
		tasks:  make(chan func(context.Context)),
		quit:   make(chan struct{}),
		done:   make(chan struct{}),
		cancel: cancel,
	}
	var wg sync.WaitGroup
	for range n {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for {
				select {
				case <-p.quit:
					return
				case task := <-p.tasks:
					task(ctx)
				}
			}
		}()
	}
	go func() {
		wg.Wait()
		close(p.done)
	}()
	return p
}

// Submit hands task to a free worker. It blocks until a worker accepts the
// task, ctx ends, or the pool is shut down. A task accepted while Shutdown
// is starting still runs before Shutdown returns.
func (p *Pool) Submit(ctx context.Context, task func(context.Context)) error {
	select {
	case p.tasks <- task:
		return nil
	case <-p.quit:
		return ErrPoolClosed
	case <-ctx.Done():
		return fmt.Errorf("submit task: %w", ctx.Err())
	}
}

// Shutdown stops the pool from accepting tasks and waits for running tasks
// to finish. If ctx ends first, it cancels the context the running tasks
// received and returns ctx's error. It is safe to call more than once and
// from several goroutines.
func (p *Pool) Shutdown(ctx context.Context) error {
	p.stopOnce.Do(func() { close(p.quit) })
	select {
	case <-p.done:
		p.cancel()
		return nil
	case <-ctx.Done():
		p.cancel()
		return fmt.Errorf("shut down pool: %w", ctx.Err())
	}
}
