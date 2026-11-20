package generics_test

import (
	"context"
	"runtime"
	"slices"
	"strconv"
	"testing"
	"time"

	"example.com/golang-practices/generics"
)

func TestMapFilterReduce(t *testing.T) {
	nums := []int{1, 2, 3, 4}
	if got := generics.Map(nums, strconv.Itoa); !slices.Equal(got, []string{"1", "2", "3", "4"}) {
		t.Errorf("Map = %q", got)
	}
	if got := generics.Filter(nums, func(n int) bool { return n%2 == 0 }); !slices.Equal(got, []int{2, 4}) {
		t.Errorf("Filter = %v", got)
	}
	if got := generics.Reduce(nums, "", func(acc string, n int) string { return acc + strconv.Itoa(n) }); got != "1234" {
		t.Errorf("Reduce = %q", got)
	}
}

func TestSortedKeys(t *testing.T) {
	got := generics.SortedKeys(map[string]int{"b": 2, "c": 3, "a": 1})
	if !slices.Equal(got, []string{"a", "b", "c"}) {
		t.Fatalf("SortedKeys = %q", got)
	}
}

func TestClamp(t *testing.T) {
	if got := generics.Clamp(15, 0, 10); got != 10 {
		t.Errorf("Clamp(15, 0, 10) = %d", got)
	}
	if got := generics.Clamp(-1.5, 0, 10); got != 0 {
		t.Errorf("Clamp(-1.5, 0, 10) = %v", got)
	}
	if got := generics.Clamp("m", "a", "k"); got != "k" {
		t.Errorf(`Clamp("m", "a", "k") = %q`, got)
	}
}

func TestSumAcceptsNamedTypes(t *testing.T) {
	if got := generics.Sum([]int{1, 2, 3}); got != 6 {
		t.Errorf("Sum(ints) = %d", got)
	}
	if got := generics.Sum([]generics.Celsius{20.5, 1.5}); got != 22 {
		t.Errorf("Sum(Celsius) = %v", got)
	}
}

type id int

func (i id) String() string { return "#" + strconv.Itoa(int(i)) }

func TestJoinStrings(t *testing.T) {
	if got := generics.JoinStrings([]id{1, 2}, ", "); got != "#1, #2" {
		t.Fatalf("JoinStrings = %q", got)
	}
}

func TestStack(t *testing.T) {
	var s generics.Stack[string]
	if _, ok := s.Pop(); ok {
		t.Fatal("Pop on an empty stack reported ok")
	}
	s.Push("a")
	s.Push("b")
	if v, ok := s.Pop(); !ok || v != "b" {
		t.Fatalf("Pop = %q, %v; want b, true", v, ok)
	}
	if s.Len() != 1 {
		t.Fatalf("Len = %d, want 1", s.Len())
	}
}

func TestStageAndMerge(t *testing.T) {
	ctx := context.Background()
	a, b := make(chan int), make(chan int)
	go func() { a <- 1; close(a) }()
	go func() { b <- 2; close(b) }()

	var got []string
	for s := range generics.Stage(ctx, generics.Merge(ctx, a, b), strconv.Itoa) {
		got = append(got, s)
	}
	slices.Sort(got)
	if !slices.Equal(got, []string{"1", "2"}) {
		t.Fatalf("got %q", got)
	}
}

func TestStageAndMergeStopOnCancelWhenInputsStayOpen(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	never := make(chan int) // never closed, never sent on
	out := generics.Stage(ctx, generics.Merge(ctx, never), func(n int) int { return n })
	cancel()
	select {
	case _, ok := <-out:
		if ok {
			t.Fatal("received a value after cancel")
		}
	case <-time.After(5 * time.Second):
		t.Fatal("output channel was not closed after cancel")
	}
}

func TestMergeClosesOnCancelWhenInputsStayOpen(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	never := make(chan int) // never closed, never sent on
	out := generics.Merge(ctx, never)
	cancel()
	select {
	case _, ok := <-out:
		if ok {
			t.Fatal("received a value after cancel")
		}
	case <-time.After(5 * time.Second):
		t.Fatal("Merge did not close its output after cancel")
	}
}

func TestMergeStopsOnCancelWhenNobodyReads(t *testing.T) {
	before := runtime.NumGoroutine()
	ctx, cancel := context.WithCancel(context.Background())
	in := make(chan int)
	_ = generics.Merge(ctx, in) // nobody reads the output
	in <- 1                     // Merge has the value and now blocks sending it
	cancel()

	// Merge's goroutines must exit even though the send never completes.
	deadline := time.Now().Add(5 * time.Second)
	for runtime.NumGoroutine() > before {
		if time.Now().After(deadline) {
			t.Fatalf("%d goroutines still running after cancel, want at most %d", runtime.NumGoroutine(), before)
		}
		time.Sleep(10 * time.Millisecond)
	}
}
