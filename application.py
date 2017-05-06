from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import mkdtemp

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = mkdtemp()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    currentuser = session["user_id"]
    #retrieve list of stock owned
    stockowned = db.execute("SELECT * FROM stock WHERE user_id = :currentuser AND shares != 0", 
                                currentuser=currentuser)
    finaltotal=0
    for dic in stockowned:
        newdic = lookup(dic["symbol"])
        dic["price"] = newdic["price"]
        dic["name"] = newdic["name"]
        dic["total"] = dic["price"] * dic["shares"]
        finaltotal += dic["total"]
        dic["price"] = usd(dic["price"])
        dic["total"] = usd(dic["total"])
        
    #retrieve cash amount
    cash = db.execute("SELECT * FROM users WHERE id =:currentuser", currentuser=currentuser)[0]["cash"]
    
    finaltotal += cash
    
    return render_template("index.html",stock=stockowned, cash=usd(cash), finaltotal=usd(finaltotal))

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    #if access via POST
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        shares = 0
        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("Pls enter", "a valid shares number")
            
        if symbol == None or lookup(symbol) == None:
            return apology("Pls enter", "A valid symbol")
        if not shares > 0:
            return apology("Pls enter", "a valid shares number")
            
        price = lookup(symbol)["price"]
        
        cash = db.execute("SELECT * FROM users WHERE id =:currentuser", currentuser=session["user_id"])[0]["cash"]
        totalmoney = price * shares
        
        if totalmoney > cash:
            return apology("NO", "money")
        else:
            db.execute("UPDATE users SET cash = cash - :totalmoney WHERE id = :currentuser", 
                        totalmoney=totalmoney, currentuser=session["user_id"])
            db.execute("INSERT INTO transactions(user_id, symbol, price, shares, datetime) VALUES (:userid, :symbol, :price, :shares, CURRENT_TIMESTAMP)",
                        userid=session["user_id"], symbol=symbol, price=price, shares=shares)
            
            flash("Bought!")
            return redirect(url_for("index"))
        
    
    #else if user access via GET
    else:
        return render_template("buy.html" )

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    
    rows = db.execute("SELECT * FROM transactions WHERE user_id=:currentuser", currentuser=session["user_id"])
    
    return render_template("history.html", list=rows)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]
        

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    #if reached via GET 
    if request.method == "GET":
        return render_template("quote.html")
    #if reached via POST
    else:
        if not request.form.get("symbol"):
            return apology("Pls enter", "A valid ticker symbol")
            
        symbols = request.form.get("symbol")
        symbols = [item.strip() for item in symbols.split(",")]
        
        quotes = []
        
        for symbol in symbols:
            lkup = lookup(symbol)
            if lkup == None:
                return apology("NICE","SYMBOL")
            lkup["price"] = usd(lkup["price"])
            quotes.append(lkup)
            
        return render_template("quoted.html", list=quotes)

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    #if user visit via POST method then register them
    if request.method == "POST":
        
        #ensure usrname and password has been submitted
        if not request.form.get("username"):
            return apology("type your", "username pls")
        if not request.form.get("password"):
            return apology("type your", "password pls")
            
        #query db for user name
        rows = db.execute("SELECT * FROM users WHERE username = :username", username = request.form.get("username"))
        #if username already exist in db
        if len(rows) != 0:
            return apology("username", "is already taken")
        # else add an username and password 
        pwd = pwd_context.encrypt(request.form.get("password")) #hash the password
        db.execute("INSERT INTO users(username, hash) VALUES(:username, :pwd)", username=request.form.get("username"), pwd=pwd)
        
        currentuser = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))[0]["id"]
        session["user_id"] = currentuser
        #redirect to login
        flash("Registered")
        return redirect(url_for("index"))    
    #else user reached route via GET
    else:
        return render_template("register.html")

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
   #if user reach by POST
    if request.method == "POST":
        symbol = request.form.get("symbol").upper()
        shares = 0
        try:
            shares = int(request.form.get("shares"))
        except ValueError:
            return apology("Pls enter", "a valid shares number")
            
        if symbol == None or lookup(symbol) == None:
            return apology("Pls enter", "A valid symbol")
        if not shares > 0:
            return apology("Pls enter", "a valid shares number")
            
        price = lookup(symbol)["price"]
        
        stockowned = db.execute("SELECT * FROM stock WHERE user_id = :currentuser AND symbol=:symbol", 
                                currentuser=session["user_id"], symbol=symbol)
        if len(stockowned) == 0:
            return apology("Not enough shares", "to sell")
            
        stockowned = stockowned[0]["shares"]
        
        totalmoney = price * shares
        
        #check stock owned to see if can sell
        if stockowned < shares:
            return apology("Not enough shares", "to sell")
        #selling
        else:
            db.execute("UPDATE users SET cash = cash + :totalmoney WHERE id = :currentuser", 
                        totalmoney=totalmoney, currentuser=session["user_id"])
            db.execute("INSERT INTO transactions(user_id, symbol, price, shares, datetime) VALUES (:userid, :symbol, :price, :shares, CURRENT_TIMESTAMP)",
                        userid=session["user_id"], symbol=symbol, price=price, shares=-shares)
            flash("Sold!")
            return redirect(url_for("index"))
   
   
   #if user reach by GET
    else:
       return render_template("sell.html")

@app.route("/changepwd", methods=["GET", "POST"])
@login_required
def changepwd():
    #POST
    if request.method == "POST":
        oldpwd = request.form.get("oldpassword")
        newpwd = request.form.get("newpassword")
        
        
        # query database for username
        rows = db.execute("SELECT * FROM users WHERE id = :userid", userid=session["user_id"])

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(oldpwd, rows[0]["hash"]):
            return apology("wrong","password")
        #if pwd correct
        else:
            db.execute("UPDATE users SET hash = :newhash WHERE id = :userid", newhash=pwd_context.encrypt(newpwd), userid=session["user_id"])
            
        return redirect(url_for("index"))
        
    #if reached via GET
    else:
        return render_template("changepwd.html")