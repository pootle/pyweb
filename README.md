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

The web server and associated classes is about 250 lines of python.

There is also a small javascript file that is used by the web page to link the fields on the web page back to the app via the web server. This is about
50 lines of code

## Dependencies
Python 3.7 or later is needed. No other packages are required.

## Run the sample app
1. Use git clone or download and unzip a zip of this repository.
1. in a command / shell window:
1. cd into the folder
2. cd into examples
3. type `python3 hello_calc_web.py`
4. Note the url printed as the app starts (on windows the url isn't shown - use http://<ip address?:8000)
5. plug the url into a web browser on this or another machine

## The sample app
The app is a trivial, state based, calculator. 

It has 3 properties, 2 numbers and a function selector - 'add', 'subtract', or 'multiply'.

It has a single method, when called it returns the result of the selected funcion applied to the 2 numbers

The web front end enables all 3 of the properties to be changed, and a 4th field showing the result of the calculation.

The result automatically updates when any of the 3 properties is changed.

The web page also displays a timer based html progress bar, this is implemented in the class that extends the app to web enable it.
The class uses a [@property decorator[(https://docs.python.org/3/library/functions.html#property) is used to generate a value for the progress bar.

## The web page template
Each web page (1 in the sample app) is a file of HTML the web server uses python's string formating to fill in all the relevant variable values.

The web server code loads the template file, and uses [python's string.format](https://docs.python.org/3/library/string.html#format-string-syntax), passing the app as a parameter. This means any property of the app
can be accesed and formatted using standard python for insertion into the web page. Methods can also easily be called by providing suitable property
decorated with @property.

This gives the template direct access to the class' properties, as well as properties of classes within the app, or even dictionary antries within dicts that are part of the app's class. 
