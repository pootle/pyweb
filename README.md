# pyweb
A python oriented minimal web server to web enable python apps.

## Intro and overview
A minmalistic web server that provides a gui for Python code using a web browser. It uses the built-in python http server class and is
intended to provide the gui for apps with a single user. It enables the user to update app properties and properties updated by the app
to automatically appear on the web page.

It is intended for use purely on a local network and does not provide any security or access protection mechanisms. It should definitely NOT be
connected to the internet!

Using a web browser to provide the gui means the app can be run on a headless system, and be easily accesed from PC's, smart phones or tablets
on the local network. It also prevents the app being tied in to any particulat GUI package (such as tk or qt4), and is inteded to be much easier
to use than typical gui packages.

Using HTML with css means that there is immense flexibility to format and animate the user interface, and also means the many smart tools existing
for web browsers can be exploited.

## Dependencies
Python 3.7 or later is needed. No other packages are required.

## Run the sample app
1. Use git clone or download and unzip a zip of this repository.
1. in a command / shell window:
1. cd into the directory
1. type `python3 hello_calc.py`
2. Note the url printed as the app starts
3. plug the url into a web browser on this or another machine
## The sample app
The app is a trivial, state based, calculator. 

It has 3 properties, 2 numbers and a function selector - 'add', 'subtract', or 'multiply'.

It has a single method, when called it returns the result of the selected funcion applied to the 2 numbers

The web front end enables all 3 of the properties to be changed, and a 4th field showing the result of the calculation.

The result automatically updates when any of the 3 properties is changed.

The web page also displays a timer based html progress bar, In this case the @property decorator is used to generate a value for the progress bar.
