# Clean up
./launcher.sh stop
rm -rf ~/autofram-remote
rm -rf ../autofram-working

# Set up the bare repo
git init --bare -b main ~/autofram-remote
git remote add agent ~/autofram-remote
git push agent main

# Set up the working copy
cd ..
git clone ~/autofram-remote autofram-working
cd autofram-working
cp ../autofram/.env .

# Rebuild and run
./launcher.sh rebuild