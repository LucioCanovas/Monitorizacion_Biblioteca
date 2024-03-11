from passlib.hash import bcrypt

# Hash de los usuarios y contraseñas
hashed_user_password = bcrypt.hash("Biblioteca1$")
hashed_admin_password = bcrypt.hash("Administrador1$Biblioteca")
hashed_user = bcrypt.hash("UserBiblioteca")
hashed_admin = bcrypt.hash("AdminBiblioteca")

print("Hash del usuario 'UserBiblioteca':", hashed_user)
print("Hash de la contraseña 'Biblioteca1$':", hashed_user_password)
print("Hash del usuario 'AdminBiblioteca':", hashed_admin)
print("Hash de la contraseña 'Administrador1$Biblioteca':", hashed_admin_password)
