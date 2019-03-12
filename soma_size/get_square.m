function square = get_square(diameter)

%returns 2d vector with points on square of diameter = diameter

d = diameter;

plus_c = repmat(d,1,2*d + 1);
minus_c = repmat(-d,1,2*d+1);

s1 = [-d:d; plus_c];
s2 = [-d:d; minus_c];
s3 = [plus_c; -d:d];
s4 = [minus_c; -d:d];

square = horzcat(s1,s2,s3,s4);
