from flask import Flask, render_template, request, redirect, flash, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import secrets

app = Flask(__name__)
app.config['SECRET_KEY'] = secrets.token_hex(16)  # Change this to a random value
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://21CS30035:21CS30035@localhost/flask'

db = SQLAlchemy(app)

import psycopg2
import paramiko
import getpass
import keyring

# SSH Credentials
ssh_params = {
    'hostname': '10.5.18.70',
    'username': 'xxx',
    'password': None,
}

# Database connection parameters for PostgreSQL
db_params_postgresql = {
    'dbname': 'xxx',
    'user': 'xxx',
    'password': 'xxx',
    'host': '10.5.18.70',
    'port': '5432',
}

def get_ssh_password():
    # Try to get password from keyring
    password = keyring.get_password('ssh_tunnel', ssh_params['username'])
    if password is None:
        password = getpass.getpass("Please enter SSH password: ")
        keyring.set_password('ssh_tunnel', ssh_params['username'], password)
    return password

def connect_to_postgresql():
    ssh_params['password'] = get_ssh_password()

    # Create an SSH tunnel
    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_client.connect(**ssh_params, allow_agent=False, look_for_keys=False)

    # Set up the tunnel
    ssh_transport = ssh_client.get_transport()
    local_port = 5432  # local port to forward to PostgreSQL server
    dest_addr = (db_params_postgresql['host'], int(db_params_postgresql['port']))
    local_addr = ('localhost', local_port)
    ssh_channel = ssh_transport.open_channel('direct-tcpip', dest_addr, local_addr)

    # Connect to PostgreSQL through the tunnel
    connection = psycopg2.connect(
        database=db_params_postgresql['dbname'],
        user=db_params_postgresql['user'],
        password=db_params_postgresql['password'],
        host='10.5.18.70',
        port=local_port,
    )

    print("Connected to PostgreSQL database via SSH tunnel.")
    return connection

# Initialize the SSH connection and PostgreSQL connection when the application starts
connection = connect_to_postgresql()

def create_table():

    cursor = connection.cursor()
    
    # SQL script to create user table
    create_table_query = """
    CREATE SCHEMA IF NOT EXISTS UnivFest;

    CREATE TABLE IF NOT EXISTS UnivFest.role (
        Name varchar(50) PRIMARY KEY,
        Description varchar(100)
    );

    CREATE TABLE IF NOT EXISTS UnivFest.college (
    Name varchar(50),
    Location varchar(100),
    PRIMARY KEY (Name, Location)
    );

    CREATE TABLE IF NOT EXISTS UnivFest.user (
    Username varchar(50) PRIMARY KEY,
    Passcode varchar(50) NOT NULL,
    Appl_status varchar(20) NOT NULL DEFAULT 'NA' CHECK (Appl_status in ('Approved','NA','Applied')),
    Name varchar(50),
    Email varchar(50) NOT NULL UNIQUE,
    Phone varchar(15) NOT NULL UNIQUE,
    Food_preference boolean,
    CName varchar(50),
    CLocation varchar(50),
    RName varchar(50),
    FOREIGN KEY (CName, CLocation) REFERENCES UnivFest.college ON DELETE CASCADE,
    FOREIGN KEY (RName) REFERENCES UnivFest.role ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS UnivFest.event (
        Event_ID SERIAL PRIMARY KEY,
        Name VARCHAR(20) NOT NULL,
        Date DATE,
        Starting_time TIME,
        Max_participants INT NOT NULL,
        Budget INT,
        Type VARCHAR(20),
        CHECK (Max_participants > 0 AND Budget > 0)
    );

    CREATE TABLE IF NOT EXISTS UnivFest.organizing_team (
        Team_ID SERIAL PRIMARY KEY,
        Name VARCHAR(20) NOT NULL,
        Responsibility VARCHAR(100)
    );

    create table IF NOT EXISTS UnivFest.organizing_team_consists_users (
    Username    varchar(50),
    Team_ID    INT,
    Position  varchar(20) not null,
    foreign key (Username) references UnivFest.user on delete cascade,
    foreign key (Team_ID) references UnivFest.organizing_team on delete cascade,
    UNIQUE (Username, Team_ID)
    );


    create table IF NOT EXISTS UnivFest.organizing_team_organizes_event (
        Team_ID    INT,
        Event_ID   INT,
        foreign key (Event_ID) references UnivFest.event on delete cascade,
        foreign key (Team_ID) references UnivFest.organizing_team on delete cascade

    );

    CREATE TABLE IF NOT EXISTS UnivFest.user_participatesin_event (
    Username varchar(50),
    Event_ID INT,
    Prize_winners int,
    foreign key (Username) references UnivFest.user on delete cascade,
    foreign key (Event_ID) references UnivFest.event on delete cascade, 
    check(Prize_winners <= 3 and Prize_winners >= -1)
    );

    CREATE TABLE IF NOT EXISTS UnivFest.volunteer_applications (
    Application_ID serial PRIMARY KEY,
    Username varchar(50) NOT NULL,
    Application_Date date DEFAULT CURRENT_DATE,
    FOREIGN KEY (Username) REFERENCES UnivFest.user(Username) ON DELETE CASCADE
    );

    create table IF NOT EXISTS UnivFest.user_volunteersfor_event (
    Username    varchar(50),
    Team_ID    INT,
    foreign key (Username) references UnivFest.user on delete cascade,
    foreign key (Team_ID) references UnivFest.organizing_team on delete cascade
    );

    create table IF NOT EXISTS UnivFest.accomodation (
    Name   varchar(50),
    Capacity    int,
    primary key (Name),
    check(capacity > 0)         
    );
    create table IF NOT EXISTS UnivFest.user_requests_accomodation (
    Username    varchar(50),
    Name   varchar(50), 
    foreign key (Username) references UnivFest.user on delete cascade,
    foreign key (Name) references UnivFest.accomodation on delete cascade
    );

    """
    
    # Execute the SQL script
    cursor.execute(create_table_query)
    
    # Commit the transaction and close connection
    connection.commit()
    cursor.close()
    # connection.close()

# Call the function to create the tables
create_table()

# Function to create the Event_view
def create_event_view():
    cur = connection.cursor()
    try:
        # SQL query to create the Event_view
        create_view_query = """
            CREATE OR REPLACE VIEW UnivFest.Event_view AS
            SELECT Event_ID, Name, Date, Starting_time, Type, Max_participants
            FROM UnivFest.Event;
        """
        cur.execute(create_view_query)
        connection.commit()
        # print("Event_view created successfully.")
    except psycopg2.Error as e:
        connection.rollback()
        print("Error creating Event_view:", e)
    finally:
        cur.close()

create_event_view()

def create_admin():
    username = 'admin'
    passcode = 'admin'
    name = 'admin'
    email = 'admin@kgpian.iitkgp.ac.in'
    phone = '1234567890'
    cname = 'IITKGP'
    clocation = 'KGP'
    rname = 'admin'

    cur = connection.cursor()

    try:
        # Check if the role exists, if not, insert it
        cur.execute("SELECT 1 FROM UnivFest.role WHERE Name = %s", (rname,))
        if not cur.fetchone():
            cur.execute("INSERT INTO UnivFest.role (Name, Description) VALUES (%s, %s)", (rname, rname))
        
        # Check if the college exists, if not, insert it
        cur.execute("SELECT 1 FROM UnivFest.college WHERE Name = %s AND Location = %s", (cname, clocation))
        if not cur.fetchone():
            cur.execute("INSERT INTO UnivFest.college (Name, Location) VALUES (%s, %s)", (cname, clocation))

        # Check if the admin user already exists
        cur.execute("SELECT 1 FROM UnivFest.user WHERE Username = %s", (username,))
        if cur.fetchone():
            cur.close()
        else:
            # Insert the admin user
            cur.execute("INSERT INTO UnivFest.user (Username, Passcode, Name, Email, Phone, CName, CLocation, RName) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (username, passcode, name, email, phone, cname, clocation, rname))
            
            connection.commit()
            cur.close()
    except Exception as e:
        cur.close()
        connection.rollback()
        
create_admin()


@app.route('/')
def index():
    if session.get('username') and session.get('role') == 'student':
        return redirect('/student_home')
    if session.get('username') and session.get('role') == 'ext_participant':
        return redirect('/ext_participant_home')
    if session.get('username') and session.get('role') == 'organizer':
        return redirect('/organizer_home')
    if session.get('username') and session.get('role') == 'admin':
        return redirect('/admin_home')
    return render_template("home.html")
    
@app.route('/reg', methods=['GET', 'POST'])
def reg():
    if session.get('username'):
        flash("You are already registered and logged in!")
        return redirect('/')
    if request.method == "POST":
        try:
            cur = connection.cursor()
            
            username = request.form['username']
            passcode = request.form['password']
            email = request.form['email']
            phone = request.form['phone']
            name = request.form['name']
            cname = request.form['cname']
            clocation = request.form['clocation']

            # Determine the value of rname based on email
            if 'kgpian' in email.lower() or 'iitkgp' in email.lower():
                rname = 'student'
            else:
                rname = 'ext_participant'

            # Check if passwords match
            confirm_password = request.form['confirm_password']
            if passcode != confirm_password:
                flash('Passwords do not match.', 'error')
                return redirect('/reg')  # Redirect back to registration page with error message
            
            # Check if username already exists
            cur.execute("SELECT 1 FROM UnivFest.user WHERE Username = %s", (username,))
            if cur.fetchone():
                flash('Username already exists. Please choose a different one.', 'error')
                return redirect('/reg')
            
            # Check if email already exists
            cur.execute("SELECT 1 FROM UnivFest.user WHERE Email = %s", (email,))
            if cur.fetchone():
                flash('Email already exists. Please use a different one.', 'error')
                return redirect('/reg')
            
            # Check if phone already exists
            cur.execute("SELECT 1 FROM UnivFest.user WHERE Phone = %s", (phone,))
            if cur.fetchone():
                flash('Phone number already exists. Please use a different one.', 'error')
                return redirect('/reg')

            # Check if the role exists, if not, insert it
            cur.execute("SELECT 1 FROM UnivFest.role WHERE Name = %s", (rname,))
            if not cur.fetchone():
                cur.execute("INSERT INTO UnivFest.role (Name, Description) VALUES (%s, %s)", (rname, rname))
            
            # Check if the college exists, if not, insert it
            cur.execute("SELECT 1 FROM UnivFest.college WHERE Name = %s AND Location = %s", (cname, clocation))
            if not cur.fetchone():
                cur.execute("INSERT INTO UnivFest.college (Name, Location) VALUES (%s, %s)", (cname, clocation))

            # If all checks pass, proceed with registration
            cur.execute("INSERT INTO UnivFest.user (Username, Passcode, Name, Email, Phone, CName, CLocation, RName) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                        (username, passcode, name, email, phone, cname, clocation, rname))
            connection.commit()
            flash('Registration successful. Please log in.', 'success')
            return redirect('/login')
        except psycopg2.Error as e:
            connection.rollback()
            flash("Registration failed: "+ str(e))
            return render_template("reg.html")
        
    return render_template("reg.html")

@app.route('/register_organizers', methods=['GET', 'POST'])
def register_organizers():
    if session.get('username'):
        flash("You are already registered and logged in!")
        return redirect('/')
    else:
        if request.method == "POST":
            try:
                cur = connection.cursor()
                
                username = request.form['username']
                passcode = request.form['password']
                email = request.form['email']
                phone = request.form['phone']
                name = request.form['name']
                cname = "UniFest Organizers"
                clocation = "Kharagpur"
                rname = 'organizer'
                passkey = request.form['passkey']

                # Check if passwords match
                confirm_password = request.form['confirm_password']
                if passcode != confirm_password:
                    flash('Passwords do not match.', 'error')
                    return redirect('/register_organizers')  # Redirect back to registration page with error message
                
                # Check if username already exists
                cur.execute("SELECT 1 FROM UnivFest.user WHERE Username = %s", (username,))
                if cur.fetchone():
                    flash('Username already exists. Please choose a different one.', 'error')
                    return redirect('/register_organizers')
                
                # Check if email already exists
                cur.execute("SELECT 1 FROM UnivFest.user WHERE Email = %s", (email,))
                if cur.fetchone():
                    flash('Email already exists. Please use a different one.', 'error')
                    return redirect('/register_organizers')
                
                # Check if phone already exists
                cur.execute("SELECT 1 FROM UnivFest.user WHERE Phone = %s", (phone,))
                if cur.fetchone():
                    flash('Phone number already exists. Please use a different one.', 'error')
                    return redirect('/register_organizers')
                
                # Check if PassKey is Correct
                if(passkey != "Loaded_Souls"):
                    flash('Invalid PassKey', 'error')
                    return redirect('/register_organizers')

                # Check if the role exists, if not, insert it
                cur.execute("SELECT 1 FROM UnivFest.role WHERE Name = %s", (rname,))
                if not cur.fetchone():
                    cur.execute("INSERT INTO UnivFest.role (Name, Description) VALUES (%s, %s)", (rname, rname))
                
                # Check if the college exists, if not, insert it
                cur.execute("SELECT 1 FROM UnivFest.college WHERE Name = %s AND Location = %s", (cname, clocation))
                if not cur.fetchone():
                    cur.execute("INSERT INTO UnivFest.college (Name, Location) VALUES (%s, %s)", (cname, clocation))

                # If all checks pass, proceed with registration
                cur.execute("INSERT INTO UnivFest.user (Username, Passcode, Name, Email, Phone, CName, CLocation, RName) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                            (username, passcode, name, email, phone, cname, clocation, rname))
                connection.commit()
                flash('Organizer Registration successful.', 'success')
                return redirect('/login')
            except psycopg2.Error as e:
                connection.rollback()
                flash("Registration failed: "+ str(e))
                return render_template("register_organizers.html")

    return render_template("register_organizers.html")

def fetch_user(username, passcode):
    cursor = connection.cursor()
    cursor.execute("""
        SELECT *
        FROM UnivFest.user
        WHERE Username = %s AND Passcode = %s
    """, (username, passcode))
    return cursor.fetchone()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('username'):
        flash("You are already logged in!")
        return redirect('/')
    if request.method == "POST":
        username = request.form['username']
        passcode = request.form['password']

        # Query the user
        user = fetch_user(username, passcode)

        if user:
            # User authenticated successfully
            # Login successful
            flash('Login successful.', 'success')

             # Store user information in session
            session['username'] = user[0]
            session['role'] = user[9]
            # print(session)

            rname = user[9]  # Assuming the third column is RName
            if rname == 'student':
                # Redirect to student home page
                return redirect('/student_home')
            elif rname == 'ext_participant':
                # Redirect to external participant home page
                return redirect('/ext_participant_home')
            elif rname== 'organizer':
                return redirect('/organizer_home')
            elif rname== 'admin':
                return redirect('/admin_home')
        else:
            flash('Invalid username or password', 'error')

    return render_template("login.html")

@app.route('/student_home')
def student_home():
    # Check if user is logged in as a student
    if session.get('username') and session.get('role') == 'student':
        return render_template("home_student.html", current_user= session.get('username'))
    else:
        flash('You need to login as a student first', 'error')
        return redirect('/login')

@app.route('/ext_participant_home')
def ext_participant_home():
    # Check if user is logged in as an external participant
    if session.get('username') and session.get('role') == 'ext_participant':
        return render_template("home_ext_participant.html", current_user= session.get('username'))
    else:
        flash('You need to login as an external participant first', 'error')
        return redirect('/login')
    
@app.route('/organizer_home')
def organizer_home():
    # Check if user is logged in as a organizer
    if session.get('username') and session.get('role') == 'organizer':
        return render_template("home_organizer.html", current_user= session.get('username'))
    else:
        flash('You need to login as a organizer first', 'error')
        return redirect('/login')

@app.route('/admin_home')
def admin_home():
    # Check if user is logged in as admin
    if session.get('username') and session.get('role') == 'admin':
        return render_template("home_admin.html", current_user= session.get('username'))
    else:
        flash('You need to login as a admin first', 'error')
        return redirect('/login')
    

@app.route('/logout')
def logout():
    # Clear the session when user logs out
    session.pop('username', None)
    session.pop('role', None)
    flash('You have been logged out', 'success')
    return redirect('/')


@app.route('/volunteer_application', methods=['GET', 'POST'])
def volunteer_application():
    if session.get('username') and session.get('role') == 'student':
        username = session.get('username')
        cur = connection.cursor()

        cur.execute(
            "SELECT Appl_status FROM UnivFest.user WHERE Username = %s",
            (username,)
        )
        result = cur.fetchone()
        appl_status = result[0]
        if appl_status == 'NA':
            cur.execute(
                "UPDATE UnivFest.user SET Appl_status = 'Applied' WHERE Username = %s",
                (username,)
            )
            connection.commit()
            cur.execute("INSERT INTO UnivFest.volunteer_applications (Username) VALUES (%s)", (username,))
            connection.commit()
            flash('Application submitted successfully', 'success')

        elif appl_status == 'Applied':
            flash('Already applied', 'success')

        elif appl_status == 'Approved':
            flash('Already a volunteer', 'message')
        else:
            flash('Unexpected application status', 'error')

        return render_template('home_student.html', current_user = username)

    else:
        flash('You need to login as an student to volunteer.', 'error')
        return redirect('/login')


@app.route('/list_org_team')
def list_org_team():
    if session.get('username'):
        if session.get('role') == 'admin':
            teams = []
            team_members = []
            cur = connection.cursor()

            try:
                cur.execute("""SELECT 
                                    ot.Team_id, 
                                    ot.Name, 
                                    ot.Responsibility,
                                    array_agg(concat(e.Event_ID, ' - ', e.Name)) AS Event_Details
                               FROM 
                                    UnivFest.organizing_team ot
                               LEFT JOIN 
                                    UnivFest.organizing_team_organizes_event otoe 
                               ON 
                                    ot.Team_ID = otoe.Team_ID
                               LEFT JOIN 
                                    UnivFest.event e 
                               ON 
                                    otoe.Event_ID = e.Event_ID
                               GROUP BY 
                                    ot.Team_id, ot.Name, ot.Responsibility;
                            """)
                team_data = cur.fetchall()

                # Assuming Starting_time needs conversion from string to datetime.time object
                teams = [
                    {'team_id': team_id,
                     'name': name,
                     'responsibility': responsibility,
                     'event_details': event_details
                     }
                    for team_id, name, responsibility, event_details in team_data
                ]

                cur.execute("""
                    SELECT ot.Team_ID, ot.Username, ot.Position
                    FROM UnivFest.organizing_team_consists_users AS ot
                """)
                team_members_data = cur.fetchall()

                team_members = [
                    {'team_id': team_id,
                     'Username': Username,
                     'position': position,
                     }
                    for team_id, Username, position in team_members_data
                ]

                connection.commit()

            except Exception as e:
                flash('Error in fetching data.', 'error')
                connection.rollback()
            finally:
                cur.close()
            return render_template('list_org_team.html', teams=teams, team_members=team_members, user_role = session.get('role'))
        elif session.get('role') == 'organizer':
            teams = []
            team_members = []
            cur = connection.cursor()

            try:
                cur.execute("""SELECT 
                                    ot.Team_id, 
                                    ot.Name, 
                                    ot.Responsibility,
                                    array_agg(concat(e.Event_ID, ' - ', e.Name)) AS Event_Details
                               FROM 
                                    UnivFest.organizing_team ot
                               LEFT JOIN 
                                    UnivFest.organizing_team_organizes_event otoe 
                               ON 
                                    ot.Team_ID = otoe.Team_ID
                               LEFT JOIN 
                                    UnivFest.event e 
                               ON 
                                    otoe.Event_ID = e.Event_ID
                               WHERE 
                                    ot.Team_id IN (
                                        SELECT Team_ID 
                                        FROM UnivFest.organizing_team_consists_users 
                                        WHERE Username = %s
                                    )
                               GROUP BY 
                                    ot.Team_id, ot.Name, ot.Responsibility;
                            """, (session.get('username'),))
                team_data = cur.fetchall()

                # Assuming Starting_time needs conversion from string to datetime.time object
                teams = [
                    {'team_id': team_id,
                     'name': name,
                     'responsibility': responsibility,
                     'event_details': event_details
                     }
                    for team_id, name, responsibility, event_details in team_data
                ]

                cur.execute("""
                    SELECT ot.Team_ID, ot.Username, ot.Position
                    FROM UnivFest.organizing_team_consists_users AS ot
                    WHERE ot.Team_ID IN (
                        SELECT ot.Team_ID
                        FROM UnivFest.organizing_team_consists_users AS ot
                        WHERE ot.Username = %s
                    )
                """, (session.get('username'),))

                team_members_data = cur.fetchall()

                team_members = [
                    {'team_id': team_id,
                     'Username': Username,
                     'position': position,
                     }
                    for team_id, Username, position in team_members_data
                ]

                connection.commit()

            except Exception as e:
                flash('Error in fetching data.', 'error')
                connection.rollback()
            finally:
                cur.close()
            return render_template('list_org_team.html', teams=teams, team_members=team_members, user_role = session.get('role'))
        else:
            flash('You need to login as an admin or organizer to view organizing teams.', 'error')
            return redirect('/login')
    else:
        flash('You need to login to view organizing teams.', 'error')
        return redirect('/login')



@app.route('/add_org_team', methods=['GET', 'POST'])
def add_org_team():
    if session.get('username') and (session.get('role') =='admin'):
        cur = connection.cursor()
        # Extract information from the form submission
        if request.method == 'POST':
            name = request.form['name']
            responsibility = request.form['responsibility']

            cur.execute("INSERT INTO UnivFest.organizing_team (Name, Responsibility) VALUES (%s, %s) RETURNING Team_ID;",
                        (name, responsibility))
            connection.commit()
            cur.close()
        return render_template('add_org_team.html')
    else:
        flash('You need to login as an admin to add organizing teams.', 'error')
        return redirect('/login')
    
@app.route('/add_org_team_member/<team_id>', methods=['GET', 'POST'])
def add_org_team_member(team_id):
    if session.get('username') and (session.get('role') == 'admin'):
        organiser_data = []
        cur = connection.cursor()
        team_id_int = int(team_id)
        cur.execute("""
            SELECT u.Username, u.Email
            FROM UnivFest.user AS u
            JOIN UnivFest.role AS r ON u.RName = r.Name
            LEFT JOIN UnivFest.organizing_team_consists_users AS ot ON u.Username = ot.Username AND ot.Team_ID = %s
            WHERE r.Name = 'organizer' AND ot.Username IS NULL
        """, (team_id_int,))
        organiser_data = cur.fetchall()

        organiser = [
            {
                'username': row[0], 'email': row[1], 'team_id': team_id_int
            } for row in organiser_data
        ]
        cur.close()

        if request.method == 'POST':
            # Handle event registration or cancellation
            username = request.form['username']
            position = request.form['position']

            cur = connection.cursor()

            try:
                insert_query = """
                INSERT INTO UnivFest.organizing_team_consists_users (Username, Team_ID, Position)
                VALUES (%s, %s, %s)
                ON CONFLICT (Username, Team_ID) DO NOTHING;
                """
                # Execute the insert operation
                cur.execute(insert_query, (username, team_id, position))

                connection.commit()

            except Exception as e:
                connection.rollback()
                print(f"Error: {e}")
                flash('An error occurred. Please try again.', 'error')
            finally:
                cur.close()
            linkler = '/add_org_team_member/'+ str(team_id_int)
            return redirect(linkler)

        return render_template('updateTeamMems.html', organiser=organiser, team_id=team_id)
    else:
        flash('You need to login as an admin to update organizing teams.', 'error')
        return redirect('/login')
    

#delete current team members function
@app.route('/view_delete_org_team_member/<team_id>', methods=['GET', 'POST'])
def view_delete_org_team_member(team_id):
    if session.get('username') and (session.get('role') == 'admin'):
        organiser_data = []
        cur = connection.cursor()
        team_id_int = int(team_id)
        cur.execute("""
            SELECT u.Username, u.Name, u.Email, u.Phone, ot.Position
            FROM UnivFest.user AS u
            JOIN UnivFest.role AS r ON u.RName = r.Name
            JOIN UnivFest.organizing_team_consists_users AS ot ON u.Username = ot.Username
            WHERE r.Name = 'organizer' AND ot.Team_ID = %s;
        """, (team_id_int,))
        organiser_data = cur.fetchall()

        organiser = [
            {
                'username': row[0], 'name': row[1], 'email': row[2], 'phone': row[3], 'position': row[4]
            } for row in organiser_data
        ]
        cur.close()

        return render_template('view_deleteTeamMems.html', organiser=organiser, team_id=team_id)
    else:
        flash('You need to login as an admin to update organizing teams.', 'error')
        return redirect('/login')
    
@app.route('/delete_org_team_member/<int:team_id>/<username>', methods=['POST'])
def delete_org_team_member(team_id, username):  # Change team_mem to username
    if session.get('username') and (session.get('role') == 'admin'):
        try:
            cur = connection.cursor()
            # Execute the delete operation
            cur.execute("""
                DELETE FROM UnivFest.organizing_team_consists_users
                WHERE Username = %s AND Team_ID = %s;
            """, (username, team_id))  # Change team_mem to username
            connection.commit()  # Commit the transaction
            flash('Team member successfully deleted.', 'success')
        except Exception as e:
            connection.rollback()
            flash('An error occurred during deletion. Please try again.', 'error')
        finally:
            cur.close()
        # Redirect back to the team member view page, assuming you have such a route
        linkler = '/view_delete_org_team_member/'+ str(team_id)
        return redirect(linkler)
    else:
        flash('You need to login as an admin to delete team members.', 'error')
        return redirect('/login')
    
  
@app.route('/update_org_team/<team_id>', methods=['GET', 'POST'])
def update_org_team(team_id):
    if session.get('username') and (session.get('role') =='admin'):
        cur = connection.cursor()
        
        # Extract information from the form submission
        if request.method == 'POST':
            name = request.form['name']
            responsibility = request.form['responsibility']

            cur.execute("UPDATE UnivFest.organizing_team SET Name = %s, Responsibility = %s WHERE Team_id = %s",
                         (name, responsibility, team_id))
            connection.commit()
            flash('Organizing team updated successfully.', 'success')
            return redirect('/list_org_team')
        
        # Fetch pre-existing information for the organizing team
        cur.execute("SELECT Name, Responsibility FROM UnivFest.organizing_team WHERE Team_id = %s", (team_id,))
        team_info = cur.fetchone()
        
        if team_info:
            team_name, team_responsibility = team_info
            cur.close()
            return render_template("update_org_team.html", team_id=team_id, team_name=team_name, team_responsibility=team_responsibility)
        else:
            cur.close()
            flash('Organizing team not found.', 'error')
            return redirect('/list_org_team')
    else:
        flash('You need to login as an admin to update organizing teams.', 'error')
        return redirect('/login')

@app.route('/delete_org_team/<team_id>', methods=['GET','POST'])
def delete_org_team(team_id):
    if session.get('username') and (session.get('role') =='admin'):
        cur = connection.cursor()
        # Extract information from the form submission
        if request.method == 'POST':
            # Get the IDs of events organized by the team
            cur.execute("SELECT Event_ID FROM UnivFest.organizing_team_organizes_event WHERE Team_ID = %s", (team_id,))
            event_ids = [row[0] for row in cur.fetchall()]

            # Delete events organized by the team from the event table
            for event_id in event_ids:
                cur.execute("DELETE FROM UnivFest.event WHERE Event_ID = %s", (event_id,))

            cur.execute("DELETE FROM UnivFest.organizing_team WHERE team_id = %s", (team_id))
            connection.commit()
        cur.close()
        return redirect('/list_org_team')
    else:
        flash('You need to login as an admin to delete organizing teams.', 'error')
        return redirect('/login')

@app.route('/view_participants/<int:team_id>', methods=['GET'])
def get_participants_and_events(team_id):
    if session.get('username'):
        cur = connection.cursor()
        check_query = """
                SELECT 1
                FROM UnivFest.organizing_team_consists_users
                WHERE Username = %s AND Team_ID = %s;
                """
        cur.execute(check_query, (session.get('username'), team_id))
        is_allowed = cur.fetchone() is not None
        if(session.get('role') == 'admin' or is_allowed):    
            # SQL query to extract participants and their event names for a given team_id
            participants = []
            try:
                query = """
                SELECT u.Name, u.Email, u.Phone, e.Name AS Event_Name
                FROM UnivFest.user u
                JOIN UnivFest.user_participatesin_event upe ON u.Username = upe.Username
                JOIN UnivFest.event e ON upe.Event_ID = e.Event_ID
                JOIN UnivFest.organizing_team_organizes_event otoe ON e.Event_ID = otoe.Event_ID
                WHERE otoe.Team_ID = %s ;
                """
                cur.execute(query, (team_id,))
                participants_data = cur.fetchall()

                participants = [
                    {'name': name, 'email': email, 'phone': phone, 'event_name': event_name}
                    for name, email, phone, event_name in participants_data
                ]

            except Exception as e:
                flash('Error viewing participants occurred.', 'error')
                connection.rollback()
                return redirect('/list_org_team')  # Ensure you have a route to handle '/error'
            finally:
                cur.close()
                # Render the HTML template with participants data
                return render_template('view_participants.html', participants=participants)
        else:
            flash('Not allowed to view the participant list for this team.', 'error')
            return redirect('/list_org_team')
    else:
        flash('You need to login as an admin/organiser to view the volunteer list.', 'error')
        return redirect('/login')
    
#Event list by organiser and admin
@app.route('/events')
def list_events():
    if session.get('username') and (session.get('role') == 'organizer' or session.get('role') =='admin'):
        events = []
        cur = connection.cursor()
        
        try:
            cur.execute("""SELECT
                    e.Event_ID,
                    e.Name,
                    e.Date,
                    e.Starting_time,
                    e.Max_participants,
                    e.Budget,
                    e.Type,
                    ot.Team_ID,
                    ot.Name AS Organizer_Team_Name,
                    ot.Responsibility AS Organizer_Team_Responsibility,
                    (e.Max_participants - COUNT(upe.Event_ID)) AS Remaining_spots
                FROM
                    UnivFest.event e
                JOIN
                    UnivFest.organizing_team_organizes_event otoe ON e.Event_ID = otoe.Event_ID
                JOIN
                    UnivFest.organizing_team ot ON otoe.Team_ID = ot.Team_ID
                LEFT JOIN
                    UnivFest.user_participatesin_event upe ON e.Event_ID = upe.Event_ID
                GROUP BY
                    e.Event_ID, ot.Team_ID;
            """)
            
            events_data = cur.fetchall()

            events = [
                {'event_id': row[0], 'name': row[1], 'date': row[2], 
                'starting_time': row[3],
                'Max_participants': row[4], 'budget': row[5], 'event_type': row[6], 
                'team_id': row[7], 'team_name': row[8], 'team_responsibility': row[9],
                'remaining_spots': row[10]}
                for row in events_data
            ]

        except Exception as e:
            connection.rollback()
            flash('Error in fetching data.', 'error')
        finally:
            cur.close()
        return render_template('events_admin_organizer.html', events=events, current_user_role = session.get('role'))
    else:
        flash('You need to login as an admin or organizer to update or delete events.', 'error')
        return redirect('/login')


# Add an event by admin
@app.route('/add_event', methods=['GET', 'POST'])
def add_event():
    if session.get('username') and session.get('role') == 'admin':
        if request.method == 'POST':
            try:
                # Extract event details from the form
                name = request.form['name']
                date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
                starting_time = datetime.strptime(request.form['starting_time'], '%H:%M').time()
                max_participants = int(request.form['Max_participants'])
                budget = int(request.form['budget'])
                event_type = request.form['type']
                team_id = int(request.form['id'])

                # Insert the event into the database
                cur = connection.cursor()

                cur.execute("SELECT 1 FROM UnivFest.event WHERE Name = %s", (name,))
                if cur.fetchone() is not None:
                    flash('Event with this name already exists. Please choose a different name.', 'error')
                    return redirect('/add_event')

                # Check if the team exists
                cur.execute("SELECT 1 FROM UnivFest.organizing_team WHERE team_id = %s", (team_id,))
                if not cur.fetchone():
                    flash('Organizing team with this ID does not exist. Please enter a valid team ID.', 'error')
                    return redirect('/add_event')

                # Insert the event
                cur.execute("""INSERT INTO UnivFest.event (Name, Date, Starting_time, Max_participants, Budget, Type)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING Event_ID;""", 
                (name, date, starting_time, max_participants, budget, event_type))
                event_id = cur.fetchone()[0]
                cur.execute("INSERT INTO UnivFest.organizing_team_organizes_event (team_id, Event_ID) VALUES (%s, %s)", (team_id, event_id))
                connection.commit()
                cur.close()

                flash('Event added successfully.', 'success')
                return redirect('/events')
            except Exception as e:
                connection.rollback()
                flash(f'Error adding event: {str(e)}', 'error')

        return render_template('add_event.html')
    else:
        flash('You need to login as an admin to add events.', 'error')
        return redirect('/login')


# Update about an event by admin or organizer
@app.route('/update_event/<event_id>', methods=['GET', 'POST'])
def update_event(event_id):
    if session.get('username') and (session.get('role') == 'organizer' or session.get('role') =='admin'):
        cur = connection.cursor()
        current_username = session.get('username')
        is_organizer= "False"
        if session.get('role') == 'organizer':
        # Check if the organizer's team is organizing the event using JOIN
            cur.execute("""
                SELECT otoe.Team_ID
                FROM UnivFest.organizing_team_consists_users otcu
                JOIN UnivFest.organizing_team_organizes_event otoe ON otcu.Team_ID = otoe.Team_ID
                WHERE otcu.Username = %s AND otoe.Event_ID = %s
            """, (current_username, event_id))
            result = cur.fetchone()
            if result:
                is_organizer = "True"
            else:
                flash('You do not have permission to update this event as you are not organizer of this event.', 'error')
                return redirect('/events')
        if request.method == 'POST':
            # Retrieve form data
            name = request.form['name']
            date = datetime.strptime(request.form['date'], '%Y-%m-%d').date()
            starting_time = request.form['starting_time']
            Max_participants = int(request.form['Max_participants'])
            budget = int(request.form['budget'])
            event_type = request.form['type']
            team_id = int(request.form['team_id'])

            try:
                # Check if the team exists
                cur.execute("SELECT 1 FROM UnivFest.organizing_team WHERE team_id = %s", (team_id,))
                if not cur.fetchone():
                    flash('Organizing team with this ID does not exist. Please enter a valid team ID.', 'error')
                    return redirect('/events')
                # Update event details in the database
                cur.execute("UPDATE UnivFest.event SET Name = %s, Date = %s, Starting_time = %s, Max_participants = %s, Budget = %s, Type = %s WHERE Event_ID = %s",
                            (name, date, starting_time, Max_participants, budget, event_type, event_id))
                cur.execute("UPDATE UnivFest.organizing_team_organizes_event SET Team_ID = %s WHERE Event_ID = %s",(team_id,event_id))
                connection.commit()
                flash('Event updated successfully.', 'success')
            except Exception as e:
                connection.rollback()
                flash('Error updating event.', 'error')
            finally:
                cur.close()
            return redirect('/events')
        
        # Fetch existing event details to pre-fill the form
        cur.execute("SELECT e.Name, e.Date, e.Starting_time, e.Max_participants, e.Budget, e.Type, o.Team_ID FROM UnivFest.event e JOIN UnivFest.organizing_team_organizes_event o ON e.Event_ID = o.Event_ID WHERE e.Event_ID = %s", (event_id,))
        event_data = cur.fetchone()
        
        if event_data:
            event_name, event_date, event_starting_time, event_max_participants, event_budget, event_type, team_id = event_data
            return render_template('update_event.html', event_id=event_id, event_name=event_name, event_date=event_date, 
                                   event_starting_time=event_starting_time, event_max_participants=event_max_participants, 
                                   event_budget=event_budget, event_type=event_type, team_id=team_id, is_organizer=is_organizer)
        else:
            flash('Event not found.', 'error')
            return redirect('/events')
    else:
        flash('You need to login as an admin or organizer to update events.', 'error')
        return redirect('/login')
        
# Delete an event by organiser or admin
@app.route('/delete_event/<event_id>', methods=['GET', 'POST'])
def delete_event(event_id):
    if session.get('username') and (session.get('role') == 'organizer' or session.get('role') =='admin'):
        cur = connection.cursor()
        current_username = session.get('username')
        if session.get('role') == 'organizer':
        # Check if the organizer's team is organizing the event using JOIN
            cur.execute("""
                SELECT otoe.Team_ID
                FROM UnivFest.organizing_team_consists_users otcu
                JOIN UnivFest.organizing_team_organizes_event otoe ON otcu.Team_ID = otoe.Team_ID
                WHERE otcu.Username = %s AND otoe.Event_ID = %s
            """, (current_username, event_id))
            result = cur.fetchone()
            if not result:
                flash('You do not have permission to update this event as you are not organizer of this event.', 'error')
                return redirect('/events')
        if request.method == "POST":
            try:
                cur.execute("DELETE FROM UnivFest.event WHERE Event_ID = %s", (event_id,))
                connection.commit()
                flash('Event deleted successfully.', 'success')
            except Exception as e:
                connection.rollback()
                flash('Error deleting event.', 'error')
            finally:
                cur.close()
        return redirect('/events')
    else:
        flash('You need to login as an admin or organizer to update events.', 'error')
        return redirect('/login')

#Winner List
@app.route('/winners')
def winners():
    winners = []
    cur = connection.cursor()
    
    try:
        cur.execute("""
        SELECT e.Name AS event_name, u.Username, upe.Prize_winners
        FROM UnivFest.user_participatesin_event upe
        JOIN UnivFest.user u ON upe.Username = u.Username
        JOIN UnivFest.event e ON upe.Event_ID = e.Event_ID
        WHERE upe.Prize_winners >= 0
        ORDER BY e.Name, upe.Prize_winners ASC;
    """)
        winners_data = cur.fetchall()

        # Convert winners data into a list of dictionaries
        winners = [
            {'event_name': row[0], 'username': row[1], 'prize_winners': row[2]}
            for row in winners_data
        ]
        cur.close()
            
    except Exception as e:
        connection.rollback()
        flash('Error in fetching data.', 'error')
    finally:
        cur.close()
    return render_template('winners.html', winners=winners, current_user_role=session.get('role'))

# Add the prize winner
@app.route('/add_winner', methods=['GET', 'POST'])
def add_winner():
    if session.get('username') and (session.get('role') == 'organizer' or session.get('role') == 'admin'):
        cur = connection.cursor()
        try:
            if request.method == 'POST':
                event_id = int(request.form['event_id'])
                username = request.form['username']
                prize_winners = int(request.form['prize_winners'])
                
                if session.get('role') == 'organizer':
                # Check if the organizer's team is organizing the event using JOIN
                    cur.execute("""
                        SELECT otoe.Team_ID
                        FROM UnivFest.organizing_team_consists_users otcu
                        JOIN UnivFest.organizing_team_organizes_event otoe ON otcu.Team_ID = otoe.Team_ID
                        WHERE otcu.Username = %s AND otoe.Event_ID = %s
                    """, (session.get('username'), event_id))
                    result = cur.fetchone()
                    if not result:
                        flash('You do not have permission to update this event as you are not organizer of this event.', 'error')
                        return redirect('/winners')
                    
                # Check if the record exists before updating
                cur.execute("SELECT COUNT(*) FROM UnivFest.user_participatesin_event WHERE Username = %s AND Event_ID = %s", (username, event_id))
                count = cur.fetchone()[0]
                
                if count > 0:
                    query = f"""UPDATE UnivFest.user_participatesin_event
                                SET Prize_winners = '{prize_winners}'
                                WHERE UnivFest.user_participatesin_event.Username = '{username}'
                                AND UnivFest.user_participatesin_event.Event_ID = '{event_id}';"""
                    cur.execute(query)
                    connection.commit()
                    flash('Prize winner added successfully.', 'success')
                    return redirect('/winners')
                else:
                    flash('Invalid event ID or username.', 'error')
        except Exception as e:
            connection.rollback()
            flash(f'Error adding prize winner: {str(e)}', 'error')
        finally:
            cur.close()

        return render_template("add_winner.html")
    else:
        flash('You need to login as an admin or organizer to add winners.', 'error')
        return redirect('/login')

@app.route('/volunteer_selection', methods=['GET', 'POST'])
def volunteer_selection():
    if session.get('username') and (session.get('role') == 'admin' or session.get('role') == 'organizer'):
        cur = connection.cursor()
        cur.execute("""
            SELECT va.Application_ID, va.Username, va.Application_Date, u.Name, u.Email
            FROM UnivFest.volunteer_applications AS va
            JOIN UnivFest.user AS u ON va.Username = u.Username
            WHERE u.Appl_status = 'Applied'
            ORDER BY va.Application_Date DESC;
        """)
        applications = cur.fetchall()
        cur.close()
        if request.method == 'POST':
            cur = connection.cursor()
            # Process the selection of a volunteer application
            username = request.form['username']
            team_id = int(request.form['team_id'])

            cur.execute("SELECT 1 FROM UnivFest.organizing_team WHERE team_id = %s", (team_id,))
            if not cur.fetchone():
                flash('Organizing team with this ID does not exist. Please enter a valid team ID.', 'error')
                return redirect('/volunteer_selection')

            try:
                # Insert the selected volunteer application into the user_volunteersfor_event table
                if session.get('role') == 'organizer':
                    cur.execute("SELECT Team_ID FROM UnivFest.organizing_team_consists_users WHERE Username = %s",(session.get('username'),))
                    if cur.fetchone()[0]!=team_id:
                        flash('Please enter your valid team ID.', 'error')
                        return redirect('/volunteer_selection')
                cur.execute("""
                    INSERT INTO UnivFest.user_volunteersfor_event (Username, Team_ID)
                    VALUES (%s, %s);
                """, (username, team_id))

                cur.execute("""DELETE FROM UnivFest.user_participatesin_event WHERE Username = %s;""",(username, ))
                connection.commit() 
                # cur.execute(
                #     "UPDATE UnivFest.user SET RName = 'Volunteer' WHERE Username = %s",
                #     (username,)
                # )
                # connection.commit()
                cur.execute(
                    "UPDATE UnivFest.user SET Appl_status = 'Approved' WHERE Username = %s",
                    (username,)
                )

                connection.commit()
                flash('Volunteer successfully assigned to the team!', 'success')
            except Exception as e:
                connection.rollback()
                flash(f'An error occurred: {e}', 'error')
            finally:
                return redirect('/volunteer_selection')

        return render_template('list_volunteer_applications.html', applications=applications)
    else:
        flash('You need to login as an admin or organiser to select volunteer.', 'error')
        return redirect('/login')


@app.route('/add_accommodation', methods=['GET', 'POST'])
def add_accommodation():
    if session.get('role') != 'admin':
        flash('Only admins can add accommodations.', 'error')
        return redirect('/login')  # Assuming there's a login view

    if request.method == 'POST':
        cur = connection.cursor()
        name = request.form['name']
        capacity = request.form['capacity']

        try:
            capacity = int(capacity)
            if capacity > 0:
                cur.execute('INSERT INTO UnivFest.accomodation (Name, Capacity) VALUES (%s, %s)', (name, capacity))
                connection.commit()
                flash('Accommodation added successfully!', 'success')
            return redirect('/add_accommodation')
        except Exception as e:
            connection.rollback()
            flash('Error updating accomodation.', 'error')
        finally:
            cur.close()

    return render_template('add_accommodation.html')


@app.route('/view_accommodations')
def view_accommodations():
    if session.get('role') != 'admin':
        flash('Only admins can view accommodations.', 'error')
        return redirect('/login')  # Assuming there's a login view

    # Fetch accommodations from the database
    cur = connection.cursor()
    cur.execute('SELECT * FROM UnivFest.accomodation')
    accommodations_data = cur.fetchall()
    accommodations = [
        {'name': row[0], 'capacity': row[1]}
        for row in accommodations_data
    ]
    cur.close()

    # Render the HTML template with accommodations data
    return render_template('accommodation_details.html', accommodations=accommodations)

@app.route('/view_volunteer/<team_id>', methods=['GET'])
def view_volunteer(team_id):
    if session.get('username') and (session.get('role') == 'admin' or session.get('role') == 'organizer'):
        cur = connection.cursor()

        query = """
            SELECT u.Name, u.Email, u.Phone
            FROM UnivFest.user u
            JOIN UnivFest.user_volunteersfor_event v ON u.Username = v.Username
            WHERE v.Team_ID = %s;
        """
        cur.execute(query, (team_id,))
        volunteer_data = cur.fetchall()

        # It appears you meant to use volunteer_mem for rendering, so let's adjust to pass it instead.
        volunteer_mem = [
            {'Name': name, 'Email': email, 'Phone': phone}
            for name, email, phone in volunteer_data
        ]
        cur.close()
        return render_template("view_volunteer.html", volunteer_data=volunteer_mem)  # Pass volunteer_mem for rendering
    else:
        flash('You need to login as an admin/organiser to view the volunteer list.', 'error')
        return redirect('/login')

@app.route('/request_accommodation', methods=['GET', 'POST'])
def request_accommodation():
    if session.get('username') and (session.get('role') == 'ext_participant'):
        username = session.get('username')
        cur = connection.cursor()
        if request.method == 'POST':
            try:
                # Check if the user already has an accommodation
                cur.execute("SELECT * FROM UnivFest.user_requests_accomodation WHERE username = %s", (username,))
                if cur.fetchone():
                    flash("Failed to assign accommodation", 'error')

                # Find accommodations with available capacity
                cur.execute("""
                    SELECT a.name FROM UnivFest.accomodation a
                    WHERE a.capacity > (SELECT COUNT(*) FROM UnivFest.user_requests_accomodation ura WHERE ura.name = a.name)
                """)
                available_accommodations = cur.fetchall()

                if not available_accommodations:
                    flash("No available accommodations.Seats filled up", 'error')

                # Select a random accommodation from those available
                random_accommodation = random.choice(available_accommodations)[0]

                # Assign the selected accommodation to the user
                cur.execute("""
                    INSERT INTO UnivFest.user_requests_accomodation (username, name)
                    VALUES (%s, %s)
                """, (username, random_accommodation))
                connection.commit()
                flash(f"Accommodation assigned successfully to {random_accommodation}", 'success')

            except Exception as e:
                connection.rollback()
                flash("Failed to assign accommodation", 'error')

            finally:
                cur.close()

            return redirect("/request_accommodation")

        status = "na"
        cur.execute("SELECT * FROM UnivFest.user_requests_accomodation WHERE username = %s", (username,))
        if cur.fetchone():
            status = "allocated"
        preference = "na"
        cur.execute("SELECT Food_preference FROM UnivFest.user WHERE username = %s", (username,))
        pref= cur.fetchone()[0]
        if pref == True:
            preference = "Non-Veg"
        elif pref == False:
            preference = "Veg"

        cur.close()

        return render_template('accomodation.html', status=status, preference=preference)
    else:
        flash('You need to login as a external participant to view and register for events.', 'error')
        return redirect('/login')
    
@app.route('/update_food_preference', methods=['GET', 'POST'])
def update_food_preference():
    if session.get('username') and session.get('role') == 'ext_participant':
        username = session.get('username')
        cur = connection.cursor()
        if request.method == 'POST':
            food_preference = request.form['food_preference']
            status = False
            if(food_preference == "Non-Vegetarian"):
                status = True
            cur = connection.cursor()
            try:
                cur.execute("UPDATE UnivFest.user SET Food_preference = %s WHERE Username = %s",
                            (status, username))
                connection.commit()
                flash('Food preference updated successfully!', 'success')
            except Exception as e:
                connection.rollback()
                flash('Error updating food preference.', 'error')
            finally:
                cur.close()

            return redirect('/request_accommodation')
        return render_template("accomodation.html")
    else:
        flash('You need to login as a student or external participant to view and register for events.', 'error')
        return redirect('/login') 

#Event page viewed by any Participant
@app.route('/events_participants', methods=['GET', 'POST'])
def events_participants():
    if session.get('username') and (session.get('role') == 'student' or session.get('role') == 'ext_participant'):
        username = session.get('username')
        cur = connection.cursor()

        # Fetch all events along with the remaining spots
        cur.execute("""
            SELECT ev.Event_ID, ev.Name, ev.Date, ev.Starting_time, ev.Max_participants, ev.Type, 
                   (ev.Max_participants - COALESCE(reg.registered_count, 0)) as remaining_spots
            FROM UnivFest.Event_view as ev
            LEFT JOIN (
                SELECT Event_ID, COUNT(*) as registered_count
                FROM UnivFest.user_participatesin_event
                GROUP BY Event_ID
            ) as reg ON ev.Event_ID = reg.Event_ID
        """)
        events_data = cur.fetchall()

        # Fetch the user's registered events
        cur.execute("SELECT Event_ID FROM UnivFest.user_participatesin_event WHERE Username = %s", (username,))
        registered_events = [row[0] for row in cur.fetchall()]

        # Convert events data into a dictionary
        events = [
            {
                'event_id': event_id,
                'name': name,
                'date': date,
                'starting_time': datetime.strptime(starting_time, '%H:%M').time() if isinstance(starting_time, str) else starting_time,
                'max_participants': max_participants,
                'event_type': type_,
                'remaining_spots': remaining_spots,
                'registered': event_id in registered_events
            }
            for event_id, name, date, starting_time, max_participants, type_, remaining_spots in events_data
        ]

        cur.execute("SELECT Appl_status from UnivFest.user where Username = %s", (session.get('username'),))
        status = cur.fetchone()
        if status:
            status = str(status[0])
        else:
            # Handle the case where no status is found for the user
            status = "NA"

        cur.close()

        if request.method == 'POST':
            # Handle event registration or cancellation
            event_id = int(request.form['event_id'])
            action = request.form['action']

            cur = connection.cursor()
            
            if (session.get('role') in ['student'] and status == "Approved"):
                flash('You are a volunteer. You cannot participate.', 'error')
                return redirect('/events_participants')
            try:
                if action == 'register':
                    # Check if the user is already registered for the event
                    if event_id not in registered_events:
                        cur.execute("SELECT Max_participants - COUNT(upe.Event_ID) FROM UnivFest.event e LEFT JOIN UnivFest.user_participatesin_event upe ON e.Event_ID = upe.Event_ID WHERE e.Event_ID = %s GROUP BY e.Max_participants, e.Event_ID HAVING Max_participants - COUNT(upe.Event_ID) > 0;", (event_id,))
                        res = cur.fetchone()

                        if res is not None and res[0] > 0:  # Ensure there are available seats
                            cur.execute("INSERT INTO UnivFest.user_participatesin_event (Username, Event_ID, Prize_winners) VALUES (%s, %s, '-1')", (username, event_id))
                            connection.commit()
                            flash('Successfully registered for the event!', 'success')
                        else:
                            flash('No available seats for the event.', 'error')
                    else:
                        flash('You are already registered for this event.', 'error')
                elif action == 'cancel':
                    if event_id in registered_events:
                        cur.execute("DELETE FROM UnivFest.user_participatesin_event WHERE Username = %s AND Event_ID = %s", (username, event_id))
                        connection.commit()
                        flash('Successfully canceled registration for the event.', 'success')
                    else:
                        flash('You are not registered for this event.', 'error')
            except Exception as e:
                connection.rollback()
                print(f"Error registering/canceling event: {e}")
                flash('An error occurred. Please try again.', 'error')
            finally:
                cur.close()

            return redirect('/events_participants')

        return render_template('events_participants.html', events=events, status=status)
    else:
        flash('You need to login as a student or external participant to view and register for events.', 'error')
        return redirect('/login')
    

#Event page viewed without login
@app.route('/events_without_login', methods=['GET', 'POST'])
def events_without_login():
    if session.get('username') and (session.get('role') == 'student' or session.get('role') == 'ext_participant'):
        return redirect('/events_participants')
    elif session.get('username') and (session.get('role') == 'admin' or session.get('role') == 'organizer'):
        return redirect('/events')
    else:
        cur = connection.cursor()

        # Fetch all events along with the remaining spots
        cur.execute("""
            SELECT ev.Event_ID, ev.Name, ev.Date, ev.Starting_time, ev.Max_participants, ev.Type, 
                   (ev.Max_participants - COALESCE(reg.registered_count, 0)) as remaining_spots
            FROM UnivFest.Event_view as ev
            LEFT JOIN (
                SELECT Event_ID, COUNT(*) as registered_count
                FROM UnivFest.user_participatesin_event
                GROUP BY Event_ID
            ) as reg ON ev.Event_ID = reg.Event_ID
        """)
        events_data = cur.fetchall()

        # Convert events data into a dictionary
        events = [
            {
                'event_id': event_id,
                'name': name,
                'date': date,
                'starting_time': datetime.strptime(starting_time, '%H:%M').time() if isinstance(starting_time, str) else starting_time,
                'max_participants': max_participants,
                'event_type': type_,
                'remaining_spots': remaining_spots,
            }
            for event_id, name, date, starting_time, max_participants, type_, remaining_spots in events_data
        ]

        cur.close()

        if request.method == 'POST':
            return redirect('\login')

        return render_template('events_without_login.html', events=events)

@app.route('/user_manage', methods=['GET', 'POST'])
def user_manage():
    if session.get('username') and (session.get('role') == 'admin'):
        cur = connection.cursor()
        if request.method == 'POST':
            # Delete user if requested
            if 'delete_user' in request.form:
                username_to_delete = request.form['delete_user']
                cur.execute("DELETE FROM UnivFest.user WHERE Username = %s", (username_to_delete,))
                connection.commit()
                flash(f"User '{username_to_delete}' has been deleted successfully.", 'success')

        # Fetch all users except the admin with their details
        cur.execute("SELECT Username, Name, Email, Phone, CName, CLocation, RName FROM UnivFest.user WHERE Username != %s", (session['username'],))
        users = cur.fetchall()
        
        # Create a list to store user info along with additional details (organizing teams or registered events)
        users_info = []
        for user in users:
            user_info = {
                'username': user[0],
                'name': user[1],
                'email': user[2],
                'phone': user[3],
                'college_name': user[4],
                'college_location': user[5],
                'role': user[6],
                'additional_info': []
            }
            
            # Fetch additional details based on the user's role
            if user[6] == 'organizer':
                # Fetch organizing teams
                cur.execute("SELECT Name FROM UnivFest.organizing_team WHERE Team_ID IN (SELECT Team_ID FROM UnivFest.organizing_team_consists_users WHERE Username = %s)", (user[0],))
                organizing_teams = cur.fetchall()
                user_info['additional_info'] = [team[0] for team in organizing_teams]
            else:
                # Fetch registered events
                cur.execute("SELECT Name FROM UnivFest.event WHERE Event_ID IN (SELECT Event_ID FROM UnivFest.user_participatesin_event WHERE Username = %s)", (user[0],))
                registered_events = cur.fetchall()
                user_info['additional_info'] = [event[0] for event in registered_events]
            
            users_info.append(user_info)

        cur.close()
        return render_template('user_manage.html', users_info=users_info)
    else:
        flash('You need to login as an admin to manage users.', 'error')
        return redirect('/login')

import random
import email, smtplib, ssl, os

from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_otp(username, otp ,receiver_email):
    sender_email = "xxx@gmail.com"
    subject = "OTP for Forgot Username or Password in UniFest Website"

    body = "Welcome to UniFest!!!\nYour username: "+ username + "\nOTP: " + str(otp) + "\nUse this otp to reset your password and Enjoy UniFest.\n\nCheers,\nUniFest Team"

    # password = input("Type your password and press enter:")
    password = "xxx"

    # Create a multipart message and set headers
    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = receiver_email
    message["Subject"] = subject

    # Add body to email
    message.attach(MIMEText(body, "plain"))
    text = message.as_string()

    # Log in to server using secure context and send email
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, text)

# Route for forgot password
@app.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']

        # Check if email exists in the database
        cur = connection.cursor()
        cur.execute("SELECT Username FROM UnivFest.user WHERE Email = %s", (email,))
        username = cur.fetchone()[0]
        cur.close()

        if username:
            # Generate OTP
            otp = random.randint(100000,999999)
            # Send OTP to the user's email address
            send_otp(username, otp, email)
            # Store the OTP in session for verification
            session['otp'] = otp
            session['email'] = email

            flash('An OTP has been sent to your email address.', 'success')
            return redirect('/verify_otp')

        else:
            flash('Email address not found in UniFest User database.', 'error')
            return redirect('/forgot_password')
    
    return render_template('forgot_password.html')

# Route for OTP verification
@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        entered_otp = request.form['otp']
        if 'otp' in session and 'email' in session:
            if entered_otp == str(session['otp']):
                # OTP verification successful
                return redirect('/reset_password')
            else:
                flash('Incorrect OTP. Please try again.', 'error')
                return redirect('/verify_otp')
        else:
            flash('Session expired. Please try again.', 'error')
            return redirect('/forgot_password')

    return render_template('verify_otp.html')

# Route for resetting password
@app.route('/reset_password', methods=['GET', 'POST'])
def reset_password():
    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password == confirm_password:
            # Update the user's password in the database
            cur = connection.cursor()
            try:
                # Update the password in the database
                cur.execute("UPDATE UnivFest.user SET Passcode = %s WHERE Email = %s", (password, session['email']))
                connection.commit()
            except Exception as e:
                # Handle exceptions (e.g., database errors)
                print("Error updating password:", e)
            finally:
                cur.close()

            # Clear session
            session.pop('otp')
            session.pop('email')

            flash('Password reset successfully. You can now login with your new password.', 'success')
            return redirect('/login')
        else:
            flash('Passwords do not match. Please try again.', 'error')
            return redirect('/reset_password')

    return render_template('reset_password.html')


@app.route('/profile', methods= ['GET'])
def view_profile():
    if session.get('username'):
        username = session.get('username')
        role = session.get('role')
        profile_info = {}

        cur = connection.cursor()
        try:
            if role == 'admin':
                cur.execute("SELECT Username, Name, Email, Phone FROM UnivFest.user WHERE Username = %s", (username,))
                profile_info = dict(zip(('Username', 'Name', 'Email', 'Phone'), cur.fetchone()))
            elif role == 'student' or role == 'ext_participant':
                cur.execute("SELECT Username, Name, Email, Phone FROM UnivFest.user WHERE Username = %s", (username,))
                profile_info = dict(zip(('Username', 'Name', 'Email', 'Phone'), cur.fetchone()))
                # Get additional information based on the role
                cur.execute("SELECT Appl_status FROM UnivFest.user WHERE Username = %s", (username,))
                status = cur.fetchone()[0]
                
                if role == 'student' and status != 'Approved':
                    cur.execute("SELECT e.Name FROM UnivFest.user_participatesin_event upe JOIN UnivFest.event e ON upe.Event_ID = e.Event_ID WHERE upe.Username = %s", (username,))
                    profile_info['events_registered'] = [row[0] for row in cur.fetchall()]
                elif role == 'student' and status == 'Approved':
                    cur.execute("SELECT e.Name FROM UnivFest.user_volunteersfor_event uvfe JOIN UnivFest.organizing_team_organizes_event otoe ON uvfe.Team_ID = otoe.Team_ID JOIN UnivFest.event e ON otoe.Event_ID = e.Event_ID WHERE uvfe.Username = %s", (username,))
                    profile_info['events_volunteered'] = [row[0] for row in cur.fetchall()]
                elif role == 'ext_participant':
                    cur.execute("SELECT Food_preference FROM UnivFest.user WHERE Username = %s", (username,))
                    additional_info = cur.fetchone()
                    profile_info['food_preference'] = additional_info[0]
                    # Fetch accommodation information
                    cur.execute("SELECT Name FROM UnivFest.user_requests_accomodation WHERE Username = %s", (username,))
                    accommodation_info = cur.fetchone()
                    if accommodation_info:
                        profile_info['accomodation'] = accommodation_info[0]
            elif role == 'organizer':
                cur.execute("SELECT Username, Name, Email, Phone FROM UnivFest.user WHERE Username = %s", (username,))
                profile_info = dict(zip(('Username', 'Name', 'Email', 'Phone'), cur.fetchone()))
                cur.execute("SELECT e.Name FROM UnivFest.organizing_team_organizes_event otoe JOIN UnivFest.event e ON otoe.Event_ID = e.Event_ID WHERE otoe.Team_ID IN (SELECT Team_ID FROM UnivFest.organizing_team_consists_users WHERE Username = %s)", (username,))
                profile_info['events_organized'] = [row[0] for row in cur.fetchall()]
        except Exception as e:
            flash('Error in fetching profile information.', 'error')
            connection.rollback()
        finally:
            cur.close()

        return render_template('profile.html', profile_info=profile_info, role=role)
    else:
        flash('You need to login to view your profile.', 'error')
        return redirect('/login')


@app.route('/update_profile', methods=['GET', 'POST'])
def update_profile():
    if session.get('username'):
        username = session.get('username')
        role = session.get('role')

        if request.method == 'GET':
            cur = connection.cursor()
            try:
                # Fetch the user's current profile information
                cur.execute("SELECT Name, Email, Phone FROM UnivFest.user WHERE Username = %s", (username,))
                profile_info = dict(zip(('Name', 'Email', 'Phone'), cur.fetchone()))
            except Exception as e:
                connection.rollback()
                flash('Error in fetching profile information.', 'error')
            finally:
                cur.close()

            return render_template('update_profile.html', profile_info=profile_info, role=role)
        
        elif request.method == 'POST':
            new_name = request.form['name']
            new_email = request.form['email']
            new_phone = request.form['phone']

            cur = connection.cursor()
            try:
                # Update the user's profile information
                cur.execute("UPDATE UnivFest.user SET Name = %s, Email = %s, Phone = %s WHERE Username = %s", (new_name, new_email, new_phone, username))
                connection.commit()
                flash('Profile updated successfully.', 'success')
            except Exception as e:
                connection.rollback()
                flash('Error in updating profile information.', 'error')
            finally:
                cur.close()

            return redirect('/profile')
    else:
        flash('You need to login to update your profile.', 'error')
        return redirect('/login')

@app.route('/payment', methods=['GET', 'POST'])
def payment():
    return render_template('payment.html', user = session.get('username'))

if __name__ == '__main__':
    app.run(debug=True)