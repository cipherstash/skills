package concurrency

import (
	"context"
	"fmt"
)

// Job is one unit of work for RunJobs.
type Job struct {
	ID int
}

// RunJobs processes jobs in order on one background worker. It returns nil
// as soon as every job has been processed, the first processing error, or
// the context's error if ctx ends first. The worker has exited by the time
// RunJobs returns.
func RunJobs(ctx context.Context, jobs []Job, process func(context.Context, Job) error) error {
	jobCh := make(chan Job)
	errCh := make(chan error, 1) // the worker sends exactly one value, then exits
	go func() { errCh <- worker(ctx, jobCh, process) }()

	for _, j := range jobs {
		select {
		case jobCh <- j:
		case err := <-errCh:
			// The worker stopped early because a job failed or ctx ended.
			return err
		}
	}
	close(jobCh)
	return <-errCh // nil once the worker has drained jobCh
}

// worker processes jobs until jobs is closed, a job fails, or ctx ends.
func worker(ctx context.Context, jobs <-chan Job, process func(context.Context, Job) error) error {
	for {
		// select picks at random among ready cases, so check ctx first: a
		// context that has already ended must not start another job.
		if err := ctx.Err(); err != nil {
			return fmt.Errorf("worker stopped: %w", err)
		}
		select {
		case <-ctx.Done():
			return fmt.Errorf("worker stopped: %w", ctx.Err())
		case job, ok := <-jobs:
			if !ok {
				return nil // jobs closed: all work is done
			}
			if err := process(ctx, job); err != nil {
				return fmt.Errorf("process job %d: %w", job.ID, err)
			}
		}
	}
}
