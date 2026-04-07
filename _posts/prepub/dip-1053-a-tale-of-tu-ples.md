---
title: DIP 1053 - A Tale of Tuples
author: Jared Hanson

categories:
  - Compilers & Tools
  - DIPs
---

# DIP 1053: A Tale of Tu-Ples

If you’ve used D for any significant length of time, you know that the tuple situation is pretty convoluted. There are built-in tup- err... [_compile time sequences_](https://dlang.org/articles/ctarguments.html), a library-level wrapper around these sequences called [`std.meta.AliasSeq`](https://dlang.org/library/std/meta/alias_seq.html), and _a second_, and subtly different, library level wrapper in [`std.typecons.Tuple`](https://dlang.org/library/std/typecons.html). Though together these constructs get the job done, the ergonomics can be pretty clunky, to say the least. You’re often stuck accessing elements by index (`t[0]`, `t[1]`, etc.), or giving them names that you have to remember later. It works, but it isn’t exactly "Fast code, fast" when you’re fighting the syntax just to get at your data.

I’ve long argued that D is [an anti-boilerplate language](https://dlang.org/blog/2018/03/29/std-variant-is-everything-cool-about-d/). The language generally prefers the most direct and concise way to get things done; that’s why I’m so excited [about DIP 1053](https://github.com/dlang/DIPs/blob/master/DIPs/accepted/DIP1053.md), which was recently accepted. It finally brings first-class tuple Unpacking syntax (or structured bindings, for those coming from C++) directly into the language core.

### The Status Quo: "Boilerplate Hell"

Before DIP 1053, returning multiple values from a function was a multi-step ceremony. Even with `std.typecons.Tuple`, you were trapped between two equally annoying options:

1. **Manual Indexing**: Accessing `result[0]` and `result[1]`. This is a one-way ticket to bugs if you ever change the return order.
2. **Explicit Assignment**: Manually declaring variables and assigning them one by one.

It looked something like this:

```d
import std.typecons;

Tuple!(int, string) getResult() {
    return tuple(404, "Not Found");
}

void main() {
    auto res = getResult();
    int code = res[0];
    string msg = res[1];
}

```

It’s verbose, it’s tedious, and it forces you to keep track of a temporary variable (`res`) that you don't even want.

### Enter DIP 1053: "Anti-Boilerplate Heaven"

DIP 1053 changes the game by allowing the compiler to understand the structure of the data you’re receiving and "unpack" it into distinct variables in a single statement. The syntax is clean, intuitive, and - most importantly - straightforward.

#### 1. Basic Unpacking Declarations

The bread and butter of this DIP is the ability to declare new variables directly from a tuple return:

```d
void main() {
    // Unpack directly into new variables
    auto (status, message) = getResult();
    
    writeln("Status: ", status);   // 404
    writeln("Message: ", message); // "Not Found"
}

```

The compiler handles the type inference for you. `status` becomes an `int`, and `message` becomes a `string`. If you want to be explicit, you can even specify the types yourself: `(int s, string m) = getResult();`.

_Note: the unpacking declaration must specify at least one type or storage class, and the number of declarations has to match the number of elements in the tuple._

#### 2. Nested Unpacking

These unpacking declarations also support nested tuples. While the built-in compile-time sequences and `std.meta.AliasSeq` _do not_ allow nesting, `std.typecons.Tuple` _does_:

```d
auto (a, (b, c)) = tuple(1, tuple("2", 3.0));
(int a, (string b, double c)) = tuple(1, tuple("2", 3.0));
```

This looks very similar to the built-in pattern matching syntax found in languages like Swift or Rust. It allows you to scope your variables exactly where they are needed while keeping the logic flat and readable.

#### 3. Foreach Integration

DIP 1053 isn't just for function returns; it also adds support for `foreach` loops over arrays of tuples:

```d
auto arr = [tuple(1, "2"), tuple(3, "4"), tuple(5, "6")];

foreach((x, y); arr) {
    writeln(x, " ", y); // "1 2\n3 4\n5 6"
}
```

The usual `foreach` storage classes are also supported:

```
auto arr = [t(1, 2), t(3, 4)];
foreach((ref x, y); arr) {
    x = 2 * y;
}
assert(arr == [t(4, 2), t(8, 4)]);
```

And an index variable can be declared alongside the unpacking declaration:

```d
import std.typecons : t = tuple;

auto arr = [t(1, 2), t(3, 4)];

// declare index for array & unpack tuple elements
foreach(i, (x, y); arr) {
    assert(x == 2 * i + 1 && y == 2 * i + 2);
}

import std.range;

// unpack a range of nested tuples
foreach(i, (j, k); enumerate(arr)) {
    writeln(i, " ", j, " ", k); // "0 1 2\n1 3 4\n"
}
```

When iterating over Associative Arrays, the index variable can _also_ be unpacked:
```d
auto aa = [t(1, 2): "hi", t(3, 4): "bye"];
foreach ((a, b), s; aa)
    writeln(a, b, s); // "12hi\n34bye\n"
```

Finally, `static foreach` and structs/classes with `opApply` are also supported; check out the DIP for further details.

This removes the need to use `pair[0]` or the old-school `foreach(id, label; pairs)` syntax which occasionally had edge cases with complex types. It’s consistent, predictable, and, dare I say, pleasant to use.

#### 4. Unpacking Function Literal Parameters

This is where the functionality _really_ gets powerful. DIP 1053 supports unpacking for the parameters of function and delegate literals:

```d
alias dg = ((x, y), z) => writeln(x, " ", y, " ", z);
dg(tuple(1, 2), 3); // "1 2 3\n"
```

`((x, y), z) { ... }` is lowered to `(__arg0, z){ auto (x,y) = __arg0; ...}`. In general, it preserves and copies storage classes from the parameter to the unpack declaration in the function body.


```d
import std.algorithm;
[t(1, 2), t(2, 3)].map!( ((a, b)) => a + b ).each!writeln; // "3\n5\n"

auto arr = [t(1, 2), t(3, 4)];
arr.each!( ((ref x, y)){ x = 3 * y; });
assert(arr.all!( (const (x, y)) => x == 3 * y));
```

For technical reasons, regular functions don't support this kind of unpacking... yet. We hope to expand the scope of the built-in tuple syntax with future DIPs.

### Sugar Never Tasted So Good

You might dismiss the functionality introduced by DIP 1053 as mere "syntactic sugar." But in a language like D that gracefully supports everything from bare-metal programming to high level application programming to one-off scripts, sugar is what makes high-level abstractions viable.

By lowering the friction of using tuples, we encourage better API design. D prefers the most concise, direct method, and DIP 1053 is as concise and direct as it gets. It highlights why D is such a great language to use; you get faster, safer code that combines the speed of native compilation with the productivity of scripting languages.

### Final Thoughts

With DIP 1053, we’ve obviated much of the machinery that previously made tuples a chore. We've simplified our users' lives and moved one step closer being a truly "anti-boilerplate" language.

If you want to see the nitty-gritty details, I highly recommend [reading the accepted DIP](https://github.com/dlang/DIPs/blob/master/DIPs/accepted/DIP1053.md). D is a community-driven project, and we’re always looking for people to jump in and get their hands dirty.
