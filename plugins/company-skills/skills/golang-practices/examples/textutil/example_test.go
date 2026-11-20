package textutil_test

import (
	"fmt"

	"example.com/golang-practices/textutil"
)

func ExampleReverse() {
	fmt.Println(textutil.Reverse("héllo"))
	// Output: olléh
}

func ExampleRender() {
	fmt.Print(textutil.Render("Fruit", []string{"apple", "pear"}))
	// Output:
	// # Fruit
	//
	// - apple
	// - pear
}
