from InquirerPy import inquirer
from InquirerPy.base.control import Choice
from rich import print as rprint

import datetime
import sqlite3
import sys
import os
import subprocess
import time


def clear_console():
    os_name = os.name
    if os_name == 'posix':
        subprocess.run(['clear'])
    elif os_name == 'nt':
        subprocess.run(['cls'], shell=True)


class Tweeter:
    def __init__(self, target):
        '''
        Creates the target sqlite3 database if it does not already exist. Then establishes the connection to it and the Cursor object.

            Parameters:
                    target (str): Filename of database that tweeter is being opened on

        '''
        self.conn = sqlite3.connect(target)
        self.c = self.conn.cursor()
        self.user_id = None  # Initialize user_id to None since user is not logged in

    def start_screen(self):
        """
        Prompts the user to either login, sign up or exit the program.
        """
        clear_console()
        result = inquirer.select(
            message="How would you like to proceed?",
            choices=["Login", "Sign Up", "Exit"],
        ).execute()

        if result == "Login":
            self.login()
        if result == "Sign Up":
            self.sign_up()
        if result == "Exit":
            self.quit()

    def login(self):
        """Prompts the user for their user id and password then checks if the entered values
        are in the database. If the password and user id match to a user in the database proceed
        to follower feed"""
        clear_console()
        user_id = inquirer.text(
            message="Enter User ID: "
        ).execute()
        password = inquirer.secret(
            message="Enter Password: "
        ).execute()

        # Check if user_id and password pair is in users table
        self.c.execute(
            """SELECT usr FROM users WHERE usr = ? AND pwd = ?;""", (
                user_id, password)
        )

        # No user was found with matching user_id and password
        if self.c.fetchone() is None:
            rprint("[red]ERROR: Incorrect User Id or Password[red]\n")
            time.sleep(1)
            self.start_screen()

        # If the user id and password match a row in the users table
        else:
            self.user_id = user_id
            self.follow_feed()

    def sign_up(self):
        """Prompts the user to enter their name, email, city, timezone and password then generates
        a new user id and inserts the entered values as a new row in the users table"""
        clear_console()

        # Prompt for Name
        name = inquirer.text(
            message="Enter Name: "
        ).execute()

        # Prompt for Email
        email = inquirer.text(
            message="Enter Email: "
        ).execute()

        # Prompt for City
        city = inquirer.text(
            message="Enter City: "
        ).execute()

        # Prompt for timezone
        timezone = None
        # While an invalid timezone is entered prompt the user to enter again
        while type(timezone) is not float:
            try:
                timezone = float(inquirer.text(
                    message="Enter Timezone: "
                ).execute())
            except (ValueError):
                print("ERROR - Non Float Entered")
        #
        # Prompt for password
        password = inquirer.secret(
            message="Enter Password: "
        ).execute()

        self.insert_user(password, name, email, city, timezone)
        print(f"Your User Id is: {self.get_next_user_id()-1}")
        time.sleep(2)

        # Return to start screen after signing up
        self.start_screen()

    def get_next_user_id(self):
        """Generates a new user id based on the largest user id in users table"""
        self.c.execute(
            '''SELECT MAX(usr) FROM users''')
        max_id = self.c.fetchone()[0]
        next_id = 1 if max_id is None else max_id + 1

        return next_id

    def insert_user(self, pwd, name, email, city, timezone):
        """
        Inserts a new user into the users table
            Parameters:
                    pwd (str): users password
                    name (str): users name
                    email (str): users email
                    city (str): users city
                    timezone (float): users timezone
        """
        insert_sql = '''INSERT INTO users (usr, pwd, name, email, city, timezone) VALUES (?, ?, ?, ?, ?, ?)'''
        self.c.execute(insert_sql, (self.get_next_user_id(),
                                    pwd, name, email, city, timezone))
        self.conn.commit()

    def quit(self):
        """Closes the connection to the database and exits the program"""
        clear_console()
        rprint("[red]Exiting now[red]")
        time.sleep(1)
        self.conn.commit()
        self.conn.close()
        exit()

    def function_menu(self):
        """Prompts the user to select a system functionality or logout and return to the start menu"""
        clear_console()
        result = inquirer.select(
            message="\nHow would you like to proceed?",
            choices=["Follow Feed", "Search for tweets", "Search for users",
                     "Compose a tweet", "List followers", "Logout",],).execute()

        if result == "Follow Feed":
            self.follow_feed()
        elif result == "Search for tweets":
            self.search_for_tweets()
        elif result == "Search for users":
            self.search_for_users()
        elif result == "Compose a tweet":
            self.compose_tweet(return_to=self.function_menu)
        elif result == "List followers":
            self.list_followers()
        elif result == "Logout":
            self.logout()

    def search_for_users(self, page_size=5):
        '''
        Allows the user to input a keyword. Then displays all users whose name contains the keyword and users whose city but not name contain the keyword
        '''
        clear_console()
        keyword = None
        while keyword is None:

            keyword = inquirer.text(
                message="Enter Keyword: ").execute().strip()

            page = 0
            user_input = ''

            while user_input != 'x':
                clear_console()
                offset = page*page_size
                users_found = self.search_for_user_query(
                    keyword, offset=offset)

                # If no users were found matching the keyword
                if not users_found and page == 0:
                    print("No users found.")
                    time.sleep(1)
                    break
                # No more than those displayed on the previous page were found
                elif not users_found:
                    print("No more users found")
                    page -= 1
                    continue

                choices = []
                for usr, name, email, city, timezone in users_found:
                    choices.append(
                        Choice(usr, f"Name: {name}, Email: {email}, City: {city}, Timezone: {timezone}"))

                choices.append(Choice('n', "Next Page"))
                choices.append(Choice('p', "Previous Page"))
                choices.append(Choice('x', "Return to Function Menu"))

                user_input = str(inquirer.select(message="Users Found:",
                                                 choices=choices,).execute())

                # If user selects a user
                if user_input.isdigit():
                    self.show_user_info(int(user_input), name)
                # If user wants to see next page
                elif user_input.lower() == 'n':
                    page += 1
                # If user wants to see previous page
                elif user_input.lower() == 'p' and page > 0:
                    page -= 1
                # If user wants to return to function menu
                elif user_input.lower() == 'x':
                    break

        self.function_menu()

    def search_for_user_query(self, keyword, offset=0):
        """
        This performs the query used in search_for_users
            Parameters:
                    keyword (str): Keyword entered by user
                    offset (int): 

            Returns: list of 5 rows from result of query
            Issues: This combines the queries in python rather than in sql. This may cause performance issues 
                    with large data sets
        """

        # Fetch users whose name matches the keyword, sorted by name length
        self.c.execute("""
            SELECT usr, name, city, email, timezone
            FROM users
            WHERE LOWER(name) LIKE LOWER(?)
            ORDER BY LENGTH(name) ASC
        """, ('%'+keyword+'%',))
        name_matches = self.c.fetchall()

        # Fetch users whose city matches the keyword (and name does not), sorted by city length
        self.c.execute("""
            SELECT usr, name, city, email, timezone
            FROM users
            WHERE LOWER(city) LIKE LOWER(?) AND LOWER(name) NOT LIKE LOWER(?)
            ORDER BY LENGTH(city) ASC
        """, ('%'+keyword+'%', '%'+keyword+'%',))
        city_matches = self.c.fetchall()

        # Combine the results and apply offset and limit
        combined_results = name_matches + city_matches
        limited_results = combined_results[offset:offset+5]

        return limited_results

    def show_user_info(self, user_id, name):
        """
        This displays the # of tweets, followers and users being followed by a given user. It also displays
        the users three most recent tweets and allows the user to select a tweet to view tweet info, follow 
        the user, or see all their tweets.

        Parameters:
                user_id (int): user_id for user whose info is being displayed

        """

        # Get number of tweets by the user
        tweet_count_query = """SELECT COUNT(*) FROM tweets WHERE writer = ?;"""
        self.c.execute(tweet_count_query, (user_id,))
        tweet_count = self.c.fetchone()[0]

        # Get number of users being followed by the user
        following_count_query = """SELECT COUNT(*) FROM follows WHERE flwer = ?;"""
        self.c.execute(following_count_query, (user_id,))
        following_count = self.c.fetchone()[0]

        # Get number of followers for the user
        follower_count_query = """SELECT COUNT(*) FROM follows WHERE flwee = ?;"""
        self.c.execute(follower_count_query, (user_id,))
        follower_count = self.c.fetchone()[0]

        # Get up to three most recent tweets from the user
        recent_tweets_query = """
        SELECT tid, text, tdate
        FROM tweets
        WHERE writer = ?
        ORDER BY tdate DESC
        LIMIT 3;
        """
        self.c.execute(recent_tweets_query, (user_id,))
        recent_tweets = self.c.fetchall()

        choices = []
        user_input = ''

        # Displays tweet stats along with recent tweets and other options
        choices.append(Choice(None, f"Number of Tweets: {tweet_count}"))
        choices.append(
            Choice(None, f"Number of users being followed: {following_count}"))
        choices.append(Choice(None, f"Number of followers: {follower_count}"))

        # For tweet info in recent tweets add to display
        for tid, text, tdate in recent_tweets:
            choices.append(
                Choice(tid, f"Tweet ID: {tid}, Date: {tdate}, Text: {text}"))

        # Add navigation options to display
        choices.append(Choice('f', "Follow this user"))
        choices.append(Choice('s', "See all tweets from this user"))
        choices.append(Choice('x', "Return to user search"))

        while user_input != 'x':
            clear_console()
            user_input = str(inquirer.select(message=f"Options for {name}",
                                             choices=choices,).execute())
            # If user selects recent tweet show tweet options
            if user_input.isdigit():
                self.tweet_options(int(user_input))
            # if user wants to follow selected user
            elif user_input == 'f':
                self.follow_user(user_id)
            # if user wants to see all users tweets
            elif user_input == 's':
                self.see_all_tweets(int(user_id))
            # if user wants to return to previous screen
            elif user_input == 'x':
                break

    def follow_user(self, follow_user_id):
        """
        Inserts row into follows with operating user as flwer and selected user as flwee

        Parameters:
                follow_user_id (int): User id for user being followed

        """
        self.c.execute("""SELECT * FROM follows WHERE flwer = ? AND flwee = ?;""",
                       (self.user_id, follow_user_id))

        # If the operating user is not already following the selected user
        if self.c.fetchone() is None:
            self.c.execute("""INSERT INTO follows (flwer, flwee, start_date) VALUES (?, ?, ?);""",
                           (self.user_id, follow_user_id, datetime.date.today(), ))
            self.conn.commit()
            print(f"You are now following user {follow_user_id}")
        else:
            print(f"{self.user_id} is already following {follow_user_id}")

        # allows user to read result of following user
        time.sleep(1)

    def see_all_tweets(self, user_id):
        """
        Displays all of selected users tweets 
        Parameters:
                user_id (int): Selected users user id
        """
        tweets_query = """
        SELECT tid, text, tdate
        FROM tweets
        WHERE writer = ?
        ORDER BY tdate DESC;
        """

        self.c.execute(tweets_query, (user_id,))
        tweets = self.c.fetchall()

        choices = []
        user_input = ''

        for tid, text, tdate in tweets:
            choices.append(
                Choice(tid, f"Tweet ID: {tid}, Date: {tdate}, Text: {text}"))

        choices.append(Choice('x', "Return to User Info"))

        while user_input != 'x':
            clear_console()
            user_input = str(inquirer.select(message=f"All tweets from user {user_id}",
                                             choices=choices,).execute())
            # If user selects tweet
            if user_input.isdigit():
                self.tweet_options(int(user_input))
            elif user_input == 'x':
                break

    def tweet_options(self, tweet_id):
        """
        Displays actions that user can take on selected tweet
        Parameters:
                tweet_id (int): tid of selected tweet
        """
        user_input = ''
        choices = []

        while user_input != 'x':
            choices = []
            stats = self.get_tweet_statistics(tweet_id)
            choices.append(Choice(None, f"# of Retweets: {stats[0]}"))
            choices.append(Choice(None, f"# of Replies: {stats[1]}"))
            choices.append(Choice('rep', "Reply to this Tweet"))
            choices.append(Choice('ret', "Retweet this Tweet"))
            choices.append(Choice('x', "Return"))
            clear_console()
            user_input = inquirer.select(
                message="Tweet Stats", choices=choices,).execute()

            # If user wants to compose a tweet replying to seleced tweet
            if user_input == 'rep':
                self.compose_tweet(replyto=tweet_id)
                print("Reply Successful")
                time.sleep(1)
            # If user wants to retweet selected tweet
            elif user_input == 'ret':
                self.insert_retweet(tweet_id)
                print("Retweet Successful")
                time.sleep(1)
            # If user wants to return to previous screen
            elif user_input == 'x':
                break

    def get_tweet_statistics(self, tweet_id):
        """
        Gets # of retweets and replies for given tweet
        Parameters:
                tweet_id (int): tid for given tweet

        Returns:
                retweets_count (int): # of times given tweet was retweeted
                replies_count (int): # of times given tweet was replied to
        """
        # Count the number of retweets for the given tweet
        self.c.execute(
            "SELECT COUNT(*) FROM retweets WHERE tid = ?", (tweet_id,))
        retweets_count = self.c.fetchone()[0]

        # Count the number of replies for the given tweet
        self.c.execute(
            "SELECT COUNT(*) FROM tweets WHERE replyto = ?", (tweet_id,))
        replies_count = self.c.fetchone()[0]

        return retweets_count, replies_count

    def insert_retweet(self, tweet_id):
        """
        inserts a retweet to a given tweet into retweets table
        """
        currDate = datetime.date.today()

        self.c.execute("""INSERT INTO retweets (usr, tid, rdate) VALUES (?, ?, ?);""",
                       (self.user_id, tweet_id, currDate))
        self.conn.commit()

    def insert_tweet(self, writer, tdate, text, replyto=None):
        """
        inserts a tweet into the tweets table and all hashtags into mentions and hashtags table

        Parameters:
                writer (int): User id of tweeting user
                tdate (date): Date of tweet
                text (str): tweets text
                replyto (int): replyto is None if the tweet is not a reply. Otherwise it is tid of tweet being replied to
        """
        next_tweet_id = self.get_next_tweet_id()
        hashtag_keywords = [word[1:]
                            for word in text.split() if word.startswith('#')]
        self.c.execute("""INSERT INTO tweets (tid, writer, tdate, text, replyto) Values (?, ?, ?, ?, ?);""",
                       (next_tweet_id, writer, tdate, text, replyto,))

        for hashtag in hashtag_keywords:
            self.c.execute(
                """SELECT * FROM hashtags WHERE term = ?""", (hashtag,))

            if self.c.fetchone() is None:
                self.c.execute(
                    """INSERT INTO hashtags VALUES (?)""", (hashtag,))

            self.c.execute(
                """SELECT * FROM mentions WHERE term = ? AND tid = ?""", (hashtag, next_tweet_id,))

            if self.c.fetchone() is None:
                self.c.execute(
                    """INSERT into mentions VALUES (?, ?)""", (next_tweet_id, hashtag,))

        self.conn.commit()

    def compose_tweet(self, replyto=None, return_to=None):
        """
        Prompts user for tweet text and inserts the tweet

        Parameters:
            replyto (int): tid of tweet being replied to. None if not replying to tweet
            return_to (callable): If called from function menu return to function menu otherwise return to previous screen
        """
        text = None
        # While user does not input valid tweet text
        while text is None:
            text = inquirer.text(message="Enter Tweet: ").execute()

            # If user input valid tweet text
            if text is not None:
                self.insert_tweet(
                    self.user_id, datetime.date.today(), text, replyto=replyto)
                print("Tweet Posted")
                time.sleep(1)
            else:
                print("No text entered")
                time.sleep(1)

        # if called from function menu return to function menu
        if callable(return_to):
            return_to()

    def get_next_tweet_id(self):
        """
        Generate next tweet id based on max tweet id in tweets table
        """
        self.c.execute(
            '''SELECT MAX(tid) FROM tweets''')
        max_id = self.c.fetchone()[0]
        next_id = 1 if max_id is None else max_id + 1

        return next_id

    def search_for_tweets(self, page_size=5):
        """
        Prompts the user to enter keywords. Then parses keywords into hashtags and text_keywords and searches for tweets which contain the text_keywords
        in the tweets.text field.
        """
        keywords = None
        # While user has not entered valid keyword(s)
        while keywords is None:
            keywords = inquirer.text(
                message="Enter keywords separated by space(prefix with # for hashtags): ").execute().split()

            # If user entered valid keyword(s)
            if keywords is not None:
                page = 0
                user_input = ''
                choices = []

                hashtag_keywords = [word[1:]
                                    for word in keywords if word.startswith('#')]
                text_keywords = [
                    word for word in keywords if not word.startswith('#')]

                while user_input != 'x':
                    choices = []
                    clear_console()
                    tweets = self.search_for_tweets_query(
                        hashtag_keywords, text_keywords, page=page, page_size=page_size)

                    # If no tweets found matching keywords
                    if not tweets and page == 0:
                        print("No tweets found")
                        time.sleep(1)
                        break

                    # If no more tweets found
                    elif not tweets:
                        print("No more tweets found")
                        time.sleep(1)
                        page -= 1
                        continue

                    for tid, text, tdate, name, in tweets:
                        choices.append(
                            Choice(tid, f"Writer: {name}, Date: {tdate}, Text: {text}"))

                    choices.append(Choice('n', "Next Page"))
                    choices.append(Choice('p', "Previous Page"))
                    choices.append(Choice('x', "Return to Function Menu"))

                    user_input = str(inquirer.select(
                        message="Tweets Found:", choices=choices).execute())

                    # If user selects a tweet
                    if user_input.isdigit():
                        self.tweet_options(int(user_input))
                    # If user wants to see next page
                    elif user_input == 'n':
                        page += 1
                    # If user wants to see previous page and not on first page
                    elif user_input == 'p' and page > 0:
                        page -= 1
                    # If user wants to return to function menu
                    elif user_input == 'x':
                        break
        self.function_menu()

    def search_for_tweets_query(self, hashtag_keywords, text_keywords, page=0, page_size=5):
        """
        Query for search_for tweets

        Parameters:
                hashtag_keywords (list(str)): hashtags being searched for
                text_keywords (list(str)): text keywords being searched for
                page (int): current page
                page_size (int): How many tweets to display per page

        Returns:
            tweets (list(tuple(int, str, date))): Tweets found matching keywords
        """
        offset = page * page_size
        # Create dynamic query parts based on keywords
        hashtag_query_parts = [
            "SELECT tid FROM mentions WHERE LOWER(term) = LOWER(?)"]
        text_query_parts = [
            "SELECT tid FROM tweets WHERE LOWER(text) LIKE LOWER(?)"]

        # Combine query parts with bind parameters
        query_parts = []
        params = []
        if text_keywords:
            query_parts.extend(text_query_parts * len(text_keywords))
            params.extend([f'%{keyword}%' for keyword in text_keywords])

        if hashtag_keywords:
            query_parts.extend(hashtag_query_parts * len(hashtag_keywords))
            params.extend(hashtag_keywords)

        combined_query_part = " UNION ".join(query_parts)

        # Combined query
        combined_query = f"""
        SELECT tid, text, tdate, name
        FROM tweets, users
        WHERE tid IN (
            {combined_query_part}
        ) AND writer = usr
        ORDER BY tdate DESC
        LIMIT 5 OFFSET ?;
        """
        params.append(offset)

        self.c.execute(combined_query, params)
        tweets = self.c.fetchall()
        return tweets

    def list_followers(self):
        """
        Displays all users following operating user
        """
        clear_console()
        user_input = ''
        choices = []
        followers = self.get_followers()

        # If no followers found
        if not followers:
            print("You have no followers")
            time.sleep(1)

        else:

            for usr, name, email, city, timezone, start_date in followers:
                choices.append(Choice(
                    usr, f"Name: {name}, Email: {email}, City: {city}, Timezone: {timezone}, Following Since: {start_date}"))

            choices.append(Choice('x', "Return to Function Menu"))

            while user_input != 'x':
                clear_console()
                user_input = str(inquirer.select(
                    message="Your Followers:", choices=choices).execute())

                # If user selects a one of their followers
                if user_input.isdigit():
                    self.show_user_info(int(user_input), name)
                # If user wants to return to function menu
                elif user_input == 'x':
                    break

        self.function_menu()

    def get_followers(self):
        """
        Query for list_followers

        Returns: list of users following operating user and when they started following
        """
        self.c.execute(
            """SELECT usr, name, email, city, timezone, start_date FROM users, follows WHERE flwee = ? AND flwer = usr;""", (self.user_id,))
        return self.c.fetchall()

    def logout(self):
        """
        Sets operating users user id to None and returns to start screen
        """
        self.user_id = None
        print("You have logged out")
        time.sleep(1)
        self.start_screen()

    def follow_feed(self, page_size=5):
        """
        Displays tweets and retweets from users that operating user is following

        Parameters:
                page_size (int): How many results to display per page
        """
        page = 0
        user_input = ''
        choices = []

        while user_input != 'x':
            clear_console()
            choices = []
            tweets = self.get_follow_feed_tweets(
                page=page, page_size=page_size)

            if not tweets and page == 0:
                print("No tweets found in your Follow Feed")
                time.sleep(1)
                break
            elif not tweets:
                print("No more tweets found")
                time.sleep(1)
                page -= 1
                continue

            for tid, replyto, text, tdate, tweet_type, author in tweets:
                choices.append(Choice(
                    tid, f"{author} Replying to {replyto}: {text} (Date: {tdate}, Type: {tweet_type}, Author: {author})"))
            choices.append(Choice('n', "Next Page"))
            choices.append(Choice('p', "Previous Page"))
            choices.append(Choice('x', "Continue to Function Menu"))

            user_input = str(inquirer.select(
                message="Follow Feed:", choices=choices).execute())

            # If user selects a tweet or retweet
            if user_input.isdigit():
                # Display options for selected tweet or original tweet if user selected a retweet
                self.tweet_options(int(user_input))
            # If user wants to see next page
            elif user_input == 'n':
                page += 1
            # If user wants to see previous page and not on first page
            elif user_input == 'p' and page > 0:
                page -= 1
            # If user wants to continue to function menu
            elif user_input == 'x':
                break

        self.function_menu()

    def get_follow_feed_tweets(self, page=0, page_size=5):
        """
        Query for follow_feed
        """
        offset = page * page_size
        self.c.execute("""
            SELECT id, replyto, text, date, type, author FROM (
                SELECT tweets.tid AS id, tweets.text, tweets.tdate AS date, 'tweet' AS type, tweets.writer AS author, replyto
                FROM tweets
                INNER JOIN follows ON tweets.writer = follows.flwee
                WHERE follows.flwer = ?
                UNION ALL
                SELECT tweets.tid AS id, tweets.text, retweets.rdate AS date, 'retweet' AS type, retweets.usr AS author, NULL as replyto
                FROM retweets
                INNER JOIN tweets ON retweets.tid = tweets.tid
                INNER JOIN follows ON retweets.usr = follows.flwee
                WHERE follows.flwer = ?
            ) ORDER BY date DESC LIMIT ? OFFSET ?;
        """, (self.user_id, self.user_id, page_size, offset))
        return self.c.fetchall()


if __name__ == "__main__":

    tweeter = Tweeter(str(sys.argv[1]))
    tweeter.start_screen()
