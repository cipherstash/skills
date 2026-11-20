package orders

import "testing"

func TestSummarise(t *testing.T) {
	records := [][]byte{
		[]byte(`{"sku":"A1","quantity":2,"price_cents":150}`),
		[]byte(`{"sku":"B2","quantity":1,"price_cents":999}`),
	}
	got, err := Summarise(records)
	if err != nil {
		t.Fatalf("Summarise: %v", err)
	}
	want := Summary{Lines: 2, Units: 3, TotalCents: 1299}
	if got != want {
		t.Errorf("Summarise = %+v, want %+v", got, want)
	}
}

func TestSummariseRejectsABadRecord(t *testing.T) {
	records := [][]byte{
		[]byte(`{"sku":"A1","quantity":2,"price_cents":150}`),
		[]byte(`{"sku":"B2","quantity":"one"}`),
	}
	if _, err := Summarise(records); err == nil {
		t.Fatal("Summarise accepted a record whose quantity is not a number")
	}
}
