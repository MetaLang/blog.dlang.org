---
title: The Amazing Compile-Time Metaprogramming State Machine
author: Jared Hanson

# Optional fields
#
# Use this if you want override the URL slug that's
# generated automatically from the filename
# slug: my-awesome-program-written-in-d (should be URL-friendly)
#
# Categories used for search indexing
categories:
  - Code
  - Tutorials
  - The Language
  - Metaprogramming
---

# The Amazing Compile-Time Metaprogramming State Machine

Complex object construction is a classic challenge in software engineering. When an aggregate (a `struct` or `class`) has many fields, constructors become cumbersome ("telescoping constructors"), and direct initialization leaves the door open to uninitialized data.

The traditional answer is the **Builder Pattern**. In languages like Java or C#, builders are typically runtime beasts. They validate at runtime that you’ve set mandatory fields, which means an application might crash because of a simple developer oversight.

In D, we don't like waiting for runtime to find errors.

Thanks to D's powerful template metaprogramming, compile-time introspection, and generative capabilities, we can engineer a **static** builder. This builder validates your object construction *before* the compiler emits a single byte of executable code. If you forget a required field, the code simply will not compile.

In this article, we’ll build this type-safe, compile-time builder from scratch, explaining each specialized piece of D magic along the way.

### The Aggregates we want to build

Let’s define a couple of testing aggregates. The builder we design should work equally well with both value types (`struct`) and reference types (`class`).

```d
struct NetworkConfig
{
    string host;
    int port;
    bool secure;
}

class UserProfile
{
    int id;
    string username;
    string bio = "";
}
```



## Step 1: The Initial Blueprint

The first challenge is to create a builder interface that can accept arguments for *any* field of a given aggregate without having to manually write a "setter" method for every field.

We can achieve this using D’s [`opDispatch`](https://dlang.org/spec/operatoroverloading.html#dispatch). `opDispatch` is a "magic" template method that is called by the compiler whenever you try to access a member function or field that doesn’t exist on the type. If type `MyStruct` defines an `opDispatch` template function, then accessing a function or member of `MyStruct` that it doesn't actually have, will instead be forwarded to the `opDispatch` template. Ex:

```d
import std.stdio;

struct MyStruct
{
    string opDispatch(string name)()
    {
        return name;
    }

    int opDispatch(string name)(int n)
    {
        return n;
    }
}

void main()
{
    MyStruct s;
    writeln(s.thisMemberDoesNotExist); // Prints "thisMemberDoesNotExist"
    writeln(s.thisFunctionDoesNotExist(42)); // Prints 42
}
```

We can use this to create an `opDispatch` function to intercept method calls matching the names of fields in `T`:

```d
import std.conv;
import std.traits;

struct BuilderFor(T)
{
    // Handle initialization for both classes and structs
    static if (is(T == class))
        T agg = new T();
    else static
        T agg;
    
    // opDispatch will catch calls like .host("localhost")
    auto opDispatch(string name, F)(F val)
    {
        writeln(i"Setting field '$(name)' to $(val)");
        
        // __traits(getMember) lets us set the field dynamically
        __traits(getMember, agg, name) = val;

        return this;
    }

    T build()
    {
        // For now, just return the aggregate
        return agg;
    }
}

void main()
{
    auto netConf = BuilderFor!NetworkConfig()
                        .host("localhost")
                        .port(80)
                        .secure(true)
                        .build();

    writeln(netConf); // Prints "NetworkConfig("localhost", 80, true)"
}
```

### Breaking down Step 1:

* **`opDispatch(string name)(...)`**: This catches any missing method call. The compiler automatically passes the name of the missing method as the template argument `name`.
* **`__traits(getMember, agg, name) = val;`**: Since we are operating on an instance (`agg`), we can use `__traits` to directly access and set the field value by its string name. You can think of this as essentially copy-pasting the value of `name` into the expression `agg.<member name> = val`. It's essentially a special way to convert statically-known strings to symbols at compile-time.



Not a bad first attempt, but what if we forget to initialize a field?

```d
void main()
{
    auto netConf = BuilderFor!NetworkConfig()
                        .host("localhost")
                        .build();

    writeln(netConf.port); // Prints 0
}
```

Luckily, in D, all variables are default-initialized (unlike the random garbage you get in C/C++). However, for large aggregates with many fields, it's very easy to forget one. This can lead to subtle bugs or even crashes, which is not ideal.

We can do better.



## Step 2: Builder Our State Machine

Step 1 gives us a fluent interface, but it doesn't enforce mandatory fields. To do that, the builder must become a **compile-time state machine**.

We need to track which fields the user has set and which are still missing. We can achieve this by making the builder recursive: each time a field is set, the builder returns a *new type* that is "aware" that one less field needs to be initialized.

We’ll nest our implementation inside an outer template to properly initialize the field list.

```d
import std.meta; // for Erase

template BuilderFor(T)
{
    // BuilderImpl is a struct that tracks state via a variadic template parameter
    struct BuilderImpl(fields...)
    {
        T agg;

        // Note: The signature changed. We are now returning a new BuildImpl with 
        BuilderImpl!(Erase!(name, fields)) opDispatch(string name, F)(F val)
        {
            writeln(i"Setting field '$(name)' to $(val)");

            __traits(getMember, agg, name) = val;

            // We erase 'name' from the 'fields' tuple and return a NEW type!
            // 'typeof(return)' automatically figures out the long template signature.
            return typeof(return)(agg);
        }

        //What's this? See note below
        T build()()
        {
            // Now we can validate. The tuple 'fields' should be empty.
            static assert(fields.length == 0, 
                i"Cannot build $(T.stringof) before all fields are specified.".text());

            return agg;
        }
    }
    
    // Initialize the builder with all *derived* members of T.
    // derivedMembers avoids inheriting symbols from superclasses if T is a class.
    alias BuilderFor = BuilderImpl!(__traits(derivedMembers, T));
}
```

_**Note:**_ `build` was defined as a 0-argument template function. Why did we do this? It's because if it were a normal function, the `static assert` would trip right away. Making it a template function stops the compiler from compiling the function
until the template is actually instantiated - which in the case of a 0-arg template function, is usually when it's called.

### Breaking down Step 2:

* **`fields...`**: `BuilderImpl` is now a [variadic template](https://dlang.org/articles/variadic-function-templates.html). It takes a compile-time list/tuple of field names that still need to be set.
* **`Erase!(name, fields)`**: This comes from `std.meta`. It returns a new tuple identical to `fields` but with the string `name` removed.
* **`typeof(return)(agg)`**: This is a beautiful piece of DRY D code. Inside `opDispatch`, [`typeof(return)`](https://dlang.org/spec/type.html#typeof-special) refers to the type we specified in the signature: `BuilderImpl!(Erase!(name, fields))`. We are constructing an instance of this new type, passing the current aggregate instance to the new builder.



## Step 3: Enforcing constraints (optional order)

A powerful feature of this builder is the ability to enforce initialization order. This is useful for building embedded DSLs or state machines where `stepA` *must* precede `stepB`.

We’ll add a boolean flag to our outer template.

```d
// Add 'enforceFieldOrder' flag
template BuilderFor(T, bool enforceFieldOrder = false)
{
    struct BuilderImpl(fields...)
    {
        T agg;

        BuilderImpl!(Erase!(name, fields)) opDispatch(string name)(typeof(__traits(getMember, T, name)) val)
        {
            // Check the specified field's position in the list using
            // std.algorithm.among (which returns a 1-based index)
            enum fieldPos = name.among!fields;

            static assert(!enforceFieldOrder || fieldPos == 1, i"In-order field initialization was specified. Expected '$(fields[0])', not '$(name)'".text());

            // ... (setting logic)
        }
        // ... build() ...
    }

    // Creating this alias allows our BuilderImpl class to become an eponymous template member
    alias BuilderFor = BuilderImpl!(__traits(derivedMembers, T));
}
```

By asserting `fieldPos == 1`, we ensure that the user can only set the field that is currently at the head of our shrinking field list.



## Step 4: Defensive Metaprogramming (better error messages)
While our state machine works, it can be "rude" to the developer. If a user typos a field name or tries to set a field twice, the compiler reports a generic error. To avoid this, we need to add some compile-time checks to ensure that these result in compile errors.

We will rewrite opDispatch using static if as a "gatekeeper" to provide specific, human-readable error messages.

```d
import std.algorithm:

// ...

BuilderImpl!(Erase!(name, fields)) opDispatch(string name, F)(F val)
{
    // Fundamental Existence Check
    // Does the field exist on the target type T?
    enum fieldExistsInT = __traits(hasMember, T, name);

    static if (fieldExistsInT)
    {
        static if (fieldPos >= 1)
        {
            // Type check
            // Does the provided value implicitly convert to the
            // type of the field defined in the aggregate?
            alias FieldType = typeof(__traits(getMember, agg, name));
     
            static assert(is(F: FieldType), "Field '$(name)' in type $(T.stringof) has type $(FieldType.stringof), not $(F.stringof)".text());
            
            // Enforce field order and return a new builder ...
        }
        else
        {
            // The field exists in T, but not in our 'fields' tuple
            static assert(false, "Field '$(name)' cannot be initialized twice".text());
        }
    }
    else
    {
        // The field doesn't exist on the struct at all
        static assert(false, "No such field '$(name)' for type $(T.stringof)".text());
    }
}

// ...
```

Why nested static ifs? In complex templates, static assert can sometimes trigger "cascading errors." If the first assertion fails, the compiler might still try to resolve the rest of the function, triggering secondary errors about type mismatches that only confuse the user.

By using nested static if blocks, we create a validation funnel. The compiler only evaluates the "inner" logic (like type checking) if the "outer" logic (does the field exist?) passes. This ensures the developer sees exactly one, high-accuracy error message.



## Step 5: Reporting State in build()
Now, let’s make the build() failure more informative. Instead of just saying "you missed something," we can programmatically generate a list of exactly which fields were left behind.

```d
// ...

T build()()
{
    // We use .map and .joiner from std.algorithm and .to from std.conv to
    // create a clean string of the missing field names at compile-time.
    static assert(fields.length == 0, 
        "Can't build $(T.stringof) before all fields have been specified.".text(),
        "Uninitialized fields: $([fields].joiner(", ").to!string())".text());

    return agg;
}

// ...
```
By combining these checks, the builder can statically enforce our requirements at compile-time. It doesn't just prevent errors; it explains them, guiding the developer toward the correct usage pattern without ever leaving the IDE.



## Step 6: Supporting Optional Fields

The builder is functional now, but it’s too strict. If `NetworkConfig` defines `bool secure = true;`, our builder still demands the user set `secure`. For good measure, let's allow the user to annotate fields as optional.

We can use [Design by Introspection](https://www.youtube.com/watch?v=k31wZafAMhk) (DbI) to filter our remaining field list in the `build()` method. We’ll create a predicate that checks if the field is annotated with a special `@optional`
[User-Defined Attribute](https://dlang.org/spec/attribute.html#uda), and filter the final field list using that predicate. If there are any fields left in the list after it's filtered, then there must still be a non-`@optional` field that
wasn't initialized.

```d
import std.meta;

// Define a simple enum to use as our UDA
enum optional;

// ...

struct BuilderImpl(fields...)
{
    // ... opDispatch ...

    T build()()
    {
        // A field only requires initialization if it *isn't* annotated with @optional
        // We can check this using std.meta.hasUDA
        enum isRequiredField(string name) = ! hasUDA!(__traits(getMember, T, name), optional);


        // Apply a compile-time filter to our 'fields' list using Filter from std.meta
        alias requiredFields = Filter!(isRequiredField, fields);

        static assert(requiredFields.length == 0, "Missing required fields for $(T.stringof): $([requiredFields].joiner(", ").to!string())".text());
        
        return agg;
    }
}

// ...
```

### Breaking down Step 6:

* `enum optional`: In D, almost any symbol can be used as a UDA. By declaring `optional`, we can now annotate our fields like: `@optional string bio`.
* `hasUDA!(..., optional)`: This trait from `std.meta` inspects the metadata of the aggregate `T` at compile-time to see if our specific attribute is present.
* `Filter!(isRequiredField, fields)`: This performs the heavy lifting. It takes our tuple of "not-yet-called" fields and discards any that the developer explicitly labeled as `@optional`. If the resulting `requiredFields` list is empty, we're good to go.



## It's All Coming Together

With this in place, we're finally ready to take our Amazing Compile-Time Metaprogramming State Machine™ for a spin:

```d
struct NetworkConfig
{
    string host;
    int port;
    @optional bool secure = true; 
}

void main()
{
    // This now compiles! We didn't set 'secure', but it's @optional.
    auto conf = BuilderFor!NetworkConfig()
                    .host("localhost")
                    .port(80)
                    .build();
}
```

What if we try to double-initialize a field?
```d
void main()
{
    // This now compiles! We didn't set 'secure', but it's @optional.
    auto conf = BuilderFor!NetworkConfig()
                    .host("localhost")
                    .host("127.0.0.1") // Error: Field 'host' cannot be initialized twice
                    .port(80)
                    .build();
}
```

What if we provide a value of the wrong type?
```d
void main()
{
    // This now compiles! We didn't set 'secure', but it's @optional.
    auto conf = BuilderFor!NetworkConfig()
                    .host(127.001) // Error: Field 'host' in type NetworkConfig has type string, not double
                    .port(80)
                    .build();
}
```

What if we try to initialize fields out of order when `enforceFieldOrder` = `true`?
```d
void main()
{
    // This now compiles! We didn't set 'secure', but it's @optional.
    auto conf = BuilderFor!(NetworkConfig, true)()
                    .port(80) // Error: In-order field initialization was specified. Expected 'host', not 'port'
                    .host("localhost")
                    .build();
}
```

Does it work with classes in addition to structs? Hell yeah it does!
```d
void main()
{
    auto u = BuilderFor!UserProfile()
                .id(42)
                .name("Meta")
                .build();
    writeln(u.id); // Prints 42
}
```



## Conclusion

What we have engineered here is a textbook implementation of the [Typestate Pattern](https://en.wikipedia.org/wiki/Typestate_analysis) - a sophisticated architectural pattern where an object's valid operations are governed not by runtime checks, but by its compile-time type.

In a traditional implementation of the Builder pattern, the object’s state changes at runtime while its type remains static. In our D implementation, every call to `opDispatch` performs a state transition, effectively "moving" the object into an entirely new type that represents a more complete version of the final aggregate.

While other modern languages like Rust utilize move semantics and affine types to achieve typestates, D’s power lies in its robust suite of metaprogramming tools:

* Dynamic State Generation: Instead of manually defining a separate struct for every possible combination of fields (e.g., BuilderNoName, BuilderWithName), our `BuilderImpl` template generates these states "on the fly" based on the user's specific initialization path.
* Design by Introspection: By leveraging `hasUDA` and `__traits`, we introspect the target type at compile-time to discover field names, types, and metadata. This allows `BuilderFor` to adapt its codified enforcement rules to the specific structure of the aggregate it is currently constructing.
* Zero (Runtime)-Cost Abstraction: Because these transitions and validations happen exclusively during compilation, the resulting machine code is as efficient as a manual assignment. Note that this isn't _truly_ zero-cost, as it can significantly bloat the
symbol table with all the template instantiations, but at _runtime_ it's as fast as hand-written code.

By moving validation from runtime to compile-time, we have transformed the traditional Builder from a simple convenience utility into a statically-enforced guard rail.

That's the Power of D™
