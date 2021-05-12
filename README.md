# pyweb
A python oriented minimal web server to web enable python apps using Flask with extras for dynamic updating.

## Intro and overview
This uses Flask to provide the basic web server functionality, with some additional python code and a small js module.

It is intended to provide the gui for apps with a single user. It enables the user to update app properties and properties updated by the app
to automatically appear on the web page.

This is for use purely on a local network and does not provide any security or access protection mechanisms. It should definitely NOT be
connected to the internet!

Using a web browser to provide the gui means the app can be run on a headless system, and be easily accesed from PC's, smart phones or tablets
on the local network. It also prevents the app being tied in to any particulat GUI package (such as tk or qt4), and is inteded to be much easier
to use than typical gui packages.

Using HTML with css means that there is immense flexibility to format and animate the user interface, and also means the many smart tools existing
for web browsers can be exploited.

The extensions for dynamic updates are about 150 lines of python and 100 lines of js.

## Dependencies
Python 3.7 or later is needed. Flask must be installed before using.

## Run the sample app
1. Use git clone or download and unzip a zip of this repository.
1. in a command / shell window:
1. cd into the folder
1. cd into examples
1. cd into tut1
1. declare a couple of shell variables that flask expects - for example:
   1. `export FLASK_APP=tut1.py`
   2. `export FLASK_ENV=development`
1. type `flask run --host=0.0.0.0`

## The sample tut1
The app is a trivial, and shows a few fields that are updates by the app and a button that invokes a method on the app's class.

The first field shows how long the app has been running,

The second and third fields show a count of how many times the button has been pressed (and 2* that number)

These 3 fields are all updated every couple of seconds by the method `index_updates(self)` that is called by the web server every couple of seconds.

The button, when pressed calls the clickbtn1 method which updates the button press count and sets the button's text and colour. The button count fields
are updated on the refresh cycle.

Note that when the button is pressed it is disabled and only re-enabled when the web browser receives the response from the server. This is to 'debounce'
button pushes.

## The sample tut2
A very simple state based calculator
It has 3 properties, 2 numbers and a function selector - 'add', 'subtract', or 'multiply'.

It has a single method, when called it returns the result of the selected funcion applied to the 2 numbers

The web front end enables all 3 of the properties to be changed, and a 4th field showing the result of the calculation.

The result automatically updates when any of the 3 properties is changed.

The web page also displays a timer based html progress bar, this is implemented in the class that extends the app to web enable it.
The class uses a [@property decorator[(https://docs.python.org/3/library/functions.html#property) is used to generate a value for the progress bar.

[See the wiki for more](wiki)
