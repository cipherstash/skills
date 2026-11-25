package concurrency_test

import (
	"context"
	"fmt"
	"time"

	"example.com/golang-practices/concurrency"
)

func ExampleRunJobs() {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	jobs := []concurrency.Job{{ID: 1}, {ID: 2}}
	err := concurrency.RunJobs(ctx, jobs, func(ctx context.Context, j concurrency.Job) error {
		fmt.Println("processed job", j.ID)
		return nil
	})
	fmt.Println("error:", err)
	// Output:
	// processed job 1
	// processed job 2
	// error: <nil>
}
