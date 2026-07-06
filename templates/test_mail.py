import smtplib

server = smtplib.SMTP("smtp.gmail.com", 587, timeout=10)
server.starttls()

server.login(
    "ariskavina070@gmail.com",
    "ppxw lwgq iutu zgen"
)

print("Berhasil Login")

server.quit()